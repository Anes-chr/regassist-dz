"""Benchmark OCR arabe : OCR ACTUEL (Tesseract 5.5, modèle `ara` rapide installé, 400 dpi, ara+fra) contre `tessdata_best` (modèle `ara` « best », même configuration, même rendu).
Le critère n'est PAS le taux de caractères global mais les valeurs juridiques : chiffres, pourcentages, montants, dates, numéros d'articles, numéros de textes, noms propres, termes juridiques.

Deux jeux (aucun n'est une lecture humaine ; les limites sont écrites dans le rapport) :
  A. « contrôles numériques » : PDF arabes à couche texte NATIVE saine ; la couche texte sert de vérité exacte, les pages sont rendues en image (400 dpi) puis passées à l'OCR.
     Limite : une page rendue proprement est plus facile qu'un scan réel.
  B. « scans problématiques » : documents arabes OCR réels (les pires de l'audit + ceux du benchmark juridique) ; la vérité des valeurs est le texte du JUMEAU FRANÇAIS (même texte
     juridique) : seules les entités numériques sont comparées (chiffres, pourcentages, montants, dates, articles, numéros de textes).
Les sorties de l'OCR sont mises en cache (results/ocr_bench/) : un second passage ne relance pas Tesseract.
Usage : python -m agent_fr.eval.ocr_bench run [--engines actuel tessdata_best] ; python -m agent_fr.eval.ocr_bench score"""
import argparse
import io
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from boa_pipeline import config as C                      # noqa: E402
from boa_pipeline.extract import normalize_chars           # noqa: E402
from boa_pipeline.ocr_entities import entity_sets, numbers  # noqa: E402

CORPUS = ROOT / "corpus"
OUT = Path(__file__).resolve().parent / "results" / "ocr_bench"
ENGINES = {"actuel": {"lang": "ara+fra", "config": ""},
           "tessdata_best": {"lang": "ara+fra", "config": "--tessdata-dir D:/llm/tessdata_best"}}
# Jeu B : pires documents de l'audit OCR (rappel des nombres < 50 %) + documents arabes du benchmark juridique (DEV/TEST v1, valeurs réglementaires)
SET_B = ["REG-25-07", "INS-04-14", "INS-07-11", "REG-92-08", "REG-94-13", "INS-01-13", "REG-09-04", "INS-08-20",
         "INS-08-25", "INS-02-26", "INS-01-26", "INS-03-26", "REG-09-01", "INS-07-21", "INS-05-21", "REG-20-03", "REG-97-04", "REG-08-04-20051223", "INS-02-21", "REG-18-01"]
SET_A_N, SET_A_PAGES = 10, 2
TWIN_OVERRIDE = {"REG-08-04-20051223": "REG-08-04-20081223"}      # jumeau arabe non rattaché dans le corpus de la phase 3 (date lue « 2005 » par l'OCR) ; rattachement démontré par le libellé du site (23 décembre 2008)


def load_docs():
    docs = {}
    for lg in ("fr", "ar"):
        for p in (CORPUS / "documents" / lg).glob("*.json"):
            d = json.loads(p.read_text(encoding="utf-8"))
            docs[d["document_id"]] = d
    return docs


def fr_twin_text(docs, work_id):
    for did, d in docs.items():
        if d["work_id"] == work_id and d["language"] == "fr" and "~" not in did:
            t = (CORPUS / d["extracted_text_path"]).read_text(encoding="utf-8")
            return did, re.sub(r"\[\[PAGE \d+\]\]", "", t)
    return None, None


def pick_sets(docs):
    set_b = []
    for w in SET_B:
        ar = next((d for did, d in docs.items() if d["work_id"] == w and d["language"] == "ar" and "~" not in did and d["extraction_method"] in ("ocr", "mixed")), None)
        fr_id, fr_txt = fr_twin_text(docs, TWIN_OVERRIDE.get(w, w)) if ar else (None, None)
        if ar and fr_txt:
            set_b.append({"document_id": ar["document_id"], "work_id": TWIN_OVERRIDE.get(w, w), "ar_work_id": w, "fr_twin": fr_id, "pages": None, "raw_path": ar["raw_path"], "page_count": ar.get("page_count")})
    cands = []
    for did, d in docs.items():
        if d["language"] != "ar" or d["extraction_method"] != "pdf_text" or "~" in did or not (2 <= (d.get("page_count") or 0) <= 8):
            continue
        txt = (CORPUS / d["extracted_text_path"]).read_text(encoding="utf-8")
        if len(txt) > 1500:
            cands.append((len(numbers(txt)), did, d))
    cands.sort(key=lambda x: (-x[0], x[1]))
    set_a = [{"document_id": did, "work_id": d["work_id"], "pages": list(range(1, SET_A_PAGES + 1)), "raw_path": d["raw_path"], "page_count": d.get("page_count")} for _, did, d in cands[:SET_A_N]]
    return set_a, set_b


def ocr_page(page, lang, config):
    import pytesseract
    from PIL import Image
    pix = page.get_pixmap(dpi=C.OCR_DPI_AR)                       # même rendu que le pipeline (400 dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    t0 = time.perf_counter()
    d = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    dt = time.perf_counter() - t0
    lines, confs, cur, key = [], [], [], None
    for i, w in enumerate(d["text"]):                              # même assemblage des mots que boa_pipeline.extract.ocr_page
        if not w.strip():
            continue
        k = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        if key is not None and k != key:
            lines.append(" ".join(cur)); cur = []
        key = k
        cur.append(w)
        if float(d["conf"][i]) >= 0:
            confs.append(float(d["conf"][i]))
    if cur:
        lines.append(" ".join(cur))
    return normalize_chars("\n".join(lines)), (sum(confs) / len(confs) if confs else None), dt


def run(engines):
    import fitz
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "sets.json").exists():                                  # sélection GELÉE : les deux moteurs sont comparés exactement sur les mêmes documents et pages
        sets = json.loads((OUT / "sets.json").read_text(encoding="utf-8"))
        set_a, set_b = sets["A"], sets["B"]
    else:
        set_a, set_b = pick_sets(load_docs())
        (OUT / "sets.json").write_text(json.dumps({"A": set_a, "B": set_b}, ensure_ascii=False, indent=1), encoding="utf-8")
    for name in engines:
        eng = ENGINES[name]
        for tag, items in (("A", set_a), ("B", set_b)):
            for it in items:
                dst = OUT / f"{name}__{it['document_id']}.json"
                if dst.exists():
                    continue
                pdf = fitz.open(CORPUS / it["raw_path"])
                pages = it["pages"] or list(range(1, pdf.page_count + 1))
                res = {"engine": name, "set": tag, "document_id": it["document_id"], "pages": []}
                for pn in pages:
                    if pn > pdf.page_count:
                        continue
                    txt, conf, dt = ocr_page(pdf[pn - 1], eng["lang"], eng["config"])
                    truth = normalize_chars(pdf[pn - 1].get_text("text")) if tag == "A" else None
                    res["pages"].append({"page": pn, "text": txt, "conf": conf, "seconds": round(dt, 2), "truth": truth})
                pdf.close()
                dst.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(name, tag, it["document_id"], len(res["pages"]), "pages", round(sum(p["seconds"] for p in res["pages"]), 1), "s", flush=True)


def cer(a: str, b: str) -> float:
    """Taux d'erreur de caractères (distance de Levenshtein / longueur de la vérité), texte normalisé (espaces, tatweel, diacritiques, chiffres indo-arabes)."""
    from boa_pipeline.ocr_entities import _plain
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[ـً-ٰٟ]", "", _plain(s))).strip()
    a, b = norm(a), norm(b)
    if not a:
        return 0.0 if not b else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


CLASSES = ["chiffres", "pourcentages", "montants", "dates", "articles", "numeros_de_textes", "noms_propres", "termes_juridiques"]


def score():
    docs = load_docs()
    sets = json.loads((OUT / "sets.json").read_text(encoding="utf-8"))
    res = {}
    for name in ENGINES:
        agg = {"A": {c: [0, 0] for c in CLASSES}, "B": {c: [0, 0] for c in CLASSES}}
        cers, secs, confs = [], [], []
        spurious = {"A": [0, 0], "B": [0, 0]}
        per_doc = {}
        excluded_a = []
        anomalies = {"unites": 0, "unites_signalees": 0, "jetons": 0, "docs_sans_jumeau": 0}
        sans_aberrant = {c: [0, 0] for c in CLASSES}                # jeu B hors REG-25-07 (42 pages, 987 nombres : domine les totaux)
        spurious_sans = [0, 0]
        for tag in ("A", "B"):
            for it in sets[tag]:
                f = OUT / f"{name}__{it['document_id']}.json"
                if not f.exists():
                    continue
                r = json.loads(f.read_text(encoding="utf-8"))
                ocr_txt = "\n".join(p["text"] for p in r["pages"])
                secs += [p["seconds"] for p in r["pages"]]
                confs += [p["conf"] for p in r["pages"] if p["conf"] is not None]
                if tag == "A":
                    truth_txt = "\n".join(p["truth"] for p in r["pages"])
                    from boa_pipeline.extract import CTRL_RE
                    if len(CTRL_RE.findall(truth_txt)) / max(1, len(truth_txt)) > 0.002:      # couche texte partiellement corrompue : ce n'est PAS une vérité exacte
                        excluded_a.append(it["document_id"])
                        secs = secs[:len(secs) - len(r["pages"])]
                        confs = confs[:len(confs) - len([p for p in r["pages"] if p["conf"] is not None])]
                        continue
                    cers += [cer(p["truth"], p["text"]) for p in r["pages"]]
                    truth = entity_sets(truth_txt, "ar")
                    truth["pourcentages"] = set()                                           # non mesurable sur le jeu A : « % » est isolé ou remplacé par un glyphe dans les couches texte arabes
                else:
                    _, fr_txt = fr_twin_text(docs, it["work_id"])
                    truth = entity_sets(fr_txt, "fr")
                    truth["noms_propres"], truth["termes_juridiques"] = set(), set()      # sans équivalent dans le jumeau français : non mesurés sur le jeu B
                got = entity_sets(ocr_txt, "ar")
                row = {}
                for c in CLASSES:
                    t, g = truth[c], got[c]
                    if t:
                        agg[tag][c][0] += len(t & g); agg[tag][c][1] += len(t)
                        row[c] = [len(t & g), len(t)]
                nums_truth = truth["chiffres"]
                nums_ocr = [n for n in numbers(ocr_txt)]
                bad = [n for n in nums_ocr if n not in nums_truth]
                spurious[tag][0] += len(bad); spurious[tag][1] += len(nums_ocr)
                row["chiffres_parasites"] = [len(bad), len(nums_ocr)]
                per_doc[it["document_id"]] = row
                if tag == "B":
                    if it["document_id"] != "REG-25-07.ar":
                        for c in CLASSES:
                            if c in row:
                                sans_aberrant[c][0] += row[c][0]; sans_aberrant[c][1] += row[c][1]
                        spurious_sans[0] += len(bad); spurious_sans[1] += len(nums_ocr)
                    # OCR_UNCERTAIN : nombre d'unités (articles) dont une valeur est signalée, par rapport au jumeau français (même détecteur pour les deux moteurs)
                    from boa_pipeline.ocr_check import unit_anomalies
                    fr_arts = {m.group(1): m.group(0) for m in []}
                    fr_units = re.split(r"(?m)^\s*(?=Article\s+\d+)", fr_txt)
                    ar_units = re.split(r"(?m)^\s*(?=(?:المادة|مادة)\s+\d+)", ocr_txt)
                    fr_by = {}
                    for u in fr_units:
                        m = re.match(r"Article\s+(\d+)", u)
                        if m:
                            fr_by.setdefault(m.group(1), u)
                    fr_all, ar_all = set(numbers(fr_txt)), set(numbers(ocr_txt))
                    for u in ar_units:
                        m = re.match(r"(?:المادة|مادة)\s+(\d+)", u)
                        if not m:
                            continue
                        an = unit_anomalies(u, fr_by.get(m.group(1)), fr_all, ar_all)
                        anomalies["unites"] += 1; anomalies["unites_signalees"] += 1 if an else 0; anomalies["jetons"] += len(an)
        res[name] = {"classes": {t: {c: (round(a / b, 3) if b else None, a, b) for c, (a, b) in agg[t].items()} for t in agg},
                     "chiffres_parasites": {t: (round(a / b, 3) if b else None, a, b) for t, (a, b) in spurious.items()},
                     "cer_jeu_A_moyen": round(statistics.mean(cers), 4) if cers else None, "exactitude_caracteres_jeu_A": round(1 - statistics.mean(cers), 4) if cers else None,
                     "secondes_par_page_moy": round(statistics.mean(secs), 2) if secs else None, "secondes_par_page_med": round(statistics.median(secs), 2) if secs else None,
                     "pages": len(secs), "confiance_moy": round(statistics.mean(confs), 1) if confs else None, "par_document": per_doc,
                     "jeu_B_hors_REG_25_07": {"classes": {c: (round(a / b, 3) if b else None, a, b) for c, (a, b) in sans_aberrant.items()},
                                              "chiffres_parasites": (round(spurious_sans[0] / spurious_sans[1], 3) if spurious_sans[1] else None, spurious_sans[0], spurious_sans[1])},
                     "jeu_B_moyenne_par_document": {c: round(statistics.mean([r[c][0] / r[c][1] for r in per_doc.values() if c in r and r[c][1]]), 3)
                                                    for c in ("chiffres", "pourcentages", "montants", "dates", "articles", "numeros_de_textes") if any(c in r and r[c][1] for r in per_doc.values())},
                     "alertes_ocr_uncertain_jeu_B": anomalies, "jeu_A_exclus_couche_texte_corrompue": excluded_a}
    dst = OUT.parent / "ocr_bench_scores.json"
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, r in res.items():
        print("==", name, "| exactitude caractères (jeu A) :", r["exactitude_caracteres_jeu_A"], "| s/page", r["secondes_par_page_moy"], "| pages", r["pages"])
        for t in ("A", "B"):
            print("  jeu", t, {c: v[0] for c, v in r["classes"][t].items()}, "| chiffres parasites", r["chiffres_parasites"][t])
    print("écrit :", dst)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "score", "sets"])
    ap.add_argument("--engines", nargs="+", default=list(ENGINES))
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.engines)
    elif a.cmd == "sets":
        sa, sb = pick_sets(load_docs())
        print(len(sa), "jeu A :", [x["document_id"] for x in sa]); print(len(sb), "jeu B :", [x["document_id"] for x in sb])
    else:
        score()
