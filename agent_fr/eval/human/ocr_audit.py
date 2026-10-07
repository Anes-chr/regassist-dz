"""Audit de la qualité du texte arabe (natif / OCR / bilingue), SANS vérité terrain : mesures indirectes et reproductibles.

Pourquoi indirect : il n'existe pas de transcription de référence. On mesure donc (1) la proportion de caractères aberrants, (2) la cohérence des chiffres, des années et du nombre
d'articles avec le JUMEAU FRANÇAIS du même texte (même work_id), (3) la présence de termes juridiques arabes attendus, (4) la validité des numéros d'article extraits.
Ces mesures bornent le problème ; elles ne remplacent pas la lecture de pages (voir docs/RETRIEVAL_PHASE3.md, échantillon visuel).
Usage : python -m agent_fr.eval.human.ocr_audit [--corpus DIR] [--out results/ocr_audit.json]
"""
import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

AR = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LAT = re.compile(r"[A-Za-zÀ-ÿ]")
DIG = re.compile(r"[0-9٠-٩۰-۹]")
OKCH = re.compile(r"[\s؀-ۿݐ-ݿA-Za-zÀ-ÿ0-9٠-٩۰-۹.,;:!?()\[\]{}'\"«»%°/\\\-–—_+=*&§#@€$‎‏‪-‮’‘“”…|<>~^`]")
INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUMTOK = re.compile(r"\d{2,}")
TERMS = ["بنك الجزائر", "النظام", "التعليمة", "المادة", "المصارف", "البنوك", "القرض", "المؤسسات", "الجريدة الرسمية", "المحافظ", "مجلس النقد", "الصرف", "الودائع",
         "الاحتياطي", "الفائدة", "المخاطر", "رأس المال", "الحسابات", "العمليات", "التصريح"]


def digits_ascii(s: str) -> str:
    return s.translate(INDIC)


def char_stats(text: str) -> dict:
    n = len(text) or 1
    letters = sum(1 for _ in AR.finditer(text)) + sum(1 for _ in LAT.finditer(text))
    bad = sum(1 for ch in text if not OKCH.match(ch) and unicodedata.category(ch)[0] not in ("Z",))
    toks = text.split()
    single = sum(1 for t in toks if len(t) == 1 and not DIG.match(t) and t not in ".,;:()-«»")
    return {"n": len(text), "ar": sum(1 for _ in AR.finditer(text)) / n, "lat": sum(1 for _ in LAT.finditer(text)) / n, "aberrant": bad / n,
            "isoles": single / max(1, len(toks)), "lettres": letters}


def _ar_ratio(text: str) -> float:
    ns = re.sub(r"[\s\d]", "", text)
    return sum(1 for _ in AR.finditer(ns)) / max(1, len(ns))


def categorize(doc: dict, chunks: list[dict]) -> str:
    if doc.get("extraction_method") == "pdf_text":
        cat = "arabe_natif"
    elif doc.get("extraction_method") == "mixed":
        cat = "arabe_mixte"
    else:
        cat = "arabe_ocr"
    txt = " ".join(c["text"] for c in chunks)
    st = char_stats(txt)
    if st["lat"] > 0.15 and st["ar"] > 0.15:
        return "bilingue_" + cat.split("_")[1]
    return cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--out", default=str(ROOT / "agent_fr" / "eval" / "results" / "ocr_audit.json"))
    a = ap.parse_args()
    from agent_fr.eval.human.bench import Corpus
    base = Path(a.corpus) if a.corpus else None
    cdir = base if base else ROOT / "corpus" / "chunks"
    ddir = base if base else ROOT / "corpus" / "metadata"
    ar_chunks = [json.loads(l) for l in open(cdir / "chunks_ar.jsonl", encoding="utf-8")]
    fr_chunks = [json.loads(l) for l in open(cdir / "chunks_fr.jsonl", encoding="utf-8")]
    ar_docs = json.loads((ddir / "documents_ar.json").read_text(encoding="utf-8"))
    ar_docs = ar_docs if isinstance(ar_docs, list) else list(ar_docs.values())
    by_ar, by_fr = defaultdict(list), defaultdict(list)
    for c in ar_chunks:
        by_ar[c["work_id"]].append(c)
    for c in fr_chunks:
        if "~" not in c["document_id"]:
            by_fr[c["work_id"]].append(c)
    rows = []
    for d in ar_docs:
        w = d["work_id"]
        ch = by_ar.get(w, [])
        if not ch:
            continue
        text = " ".join(c["text"] for c in ch)
        cs = char_stats(text)
        row = {"work_id": w, "categorie": categorize(d, ch), "chunks": len(ch), "chars": cs["n"], "aberrant": cs["aberrant"], "isoles": cs["isoles"],
               "terms": sum(1 for t in TERMS if t in text) / len(TERMS), "flags": d.get("quality_flags") or (d.get("quality") or {}).get("flags") or []}
        row["chunks_illisibles"] = sum(1 for c in ch if len(c["text"]) > 150 and _ar_ratio(c["text"]) < 0.6 and char_stats(c["text"])["lat"] < 0.15)   # couche texte arabe corrompue
        arts = [c.get("article") for c in ch if c["unit_kind"] == "article"]
        row["articles_total"] = len(arts)
        row["articles_non_numeriques"] = sum(1 for x in arts if not re.fullmatch(r"\d{1,3}( ?(bis|ter))?", digits_ascii(str(x)) if x is not None else ""))
        fr = by_fr.get(w)
        if fr:
            ftxt = " ".join(c["text"] for c in fr)
            fn = {m for m in NUMTOK.findall(ftxt)}
            an = {m for m in NUMTOK.findall(digits_ascii(text))}
            row["jumeau_fr"] = True
            row["nombres_fr"] = len(fn)
            row["rappel_nombres"] = (len(fn & an) / len(fn)) if fn else None
            fy = set(re.findall(r"\b(19[89]\d|20[0-3]\d)\b", ftxt))
            ay = set(re.findall(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)", digits_ascii(text)))
            row["rappel_annees"] = (len(fy & ay) / len(fy)) if fy else None
            fa = sum(1 for c in fr if c["unit_kind"] == "article")
            row["ratio_articles_ar_fr"] = round(len(arts) / fa, 2) if fa else None
        else:
            row["jumeau_fr"] = False
        rows.append(row)

    def summarize(rs):
        def m(key):
            v = [r[key] for r in rs if r.get(key) is not None]
            return round(statistics.mean(v), 3) if v else None
        tw = [r for r in rs if r["jumeau_fr"]]
        return {"documents": len(rs), "chunks": sum(r["chunks"] for r in rs), "caracteres_aberrants_moy": m("aberrant"), "mots_isoles_moy": m("isoles"),
                "termes_juridiques_moy": m("terms"), "avec_jumeau_fr": len(tw),
                "rappel_nombres_moy": round(statistics.mean([r["rappel_nombres"] for r in tw if r["rappel_nombres"] is not None] or [0]), 3) if tw else None,
                "rappel_annees_moy": round(statistics.mean([r["rappel_annees"] for r in tw if r["rappel_annees"] is not None] or [0]), 3) if tw else None,
                "articles_non_numeriques": f"{sum(r['articles_non_numeriques'] for r in rs)}/{sum(r['articles_total'] for r in rs)}",
                "ratio_articles_ar_fr_median": round(statistics.median([r["ratio_articles_ar_fr"] for r in tw if r.get("ratio_articles_ar_fr")] or [0]), 2) if tw else None,
                "chunks_illisibles": sum(r["chunks_illisibles"] for r in rs), "documents_avec_chunks_illisibles": sum(1 for r in rs if r["chunks_illisibles"]),
                "documents_nombres_rappel_sous_50pct": sum(1 for r in tw if r["rappel_nombres"] is not None and r["rappel_nombres"] < 0.5)}
    res = {"par_categorie": {c: summarize([r for r in rows if r["categorie"] == c]) for c in sorted({r["categorie"] for r in rows})}, "global": summarize(rows),
           "pires_documents": sorted([r for r in rows if r["jumeau_fr"] and r["rappel_nombres"] is not None], key=lambda r: r["rappel_nombres"])[:15], "documents": rows}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    for k, v in res["par_categorie"].items():
        print(k, json.dumps(v, ensure_ascii=False))
    print("global", json.dumps(res["global"], ensure_ascii=False))
    print("écrit :", a.out)


if __name__ == "__main__":
    main()
