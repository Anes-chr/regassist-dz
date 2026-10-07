"""Audit du détecteur OCR_UNCERTAIN : taux d'alertes sur les textes arabes à couche texte NATIVE (aucune erreur d'OCR possible : plancher de faux positifs dû aux différences de traduction)
et sur les textes OCR, puis échantillon d'alertes à relire (graine fixe) avec le contexte arabe et français.
Lecture seule : aucun chunk n'est modifié. Usage : python -m agent_fr.eval.ocr_alert_audit [--corpus DIR] [--n 20] [--seed 11]"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from boa_pipeline.ocr_check import unit_anomalies  # noqa: E402
from boa_pipeline.ocr_entities import numbers       # noqa: E402


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None, help="instantané plat ; par défaut le corpus vivant")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    cdir = Path(a.corpus) if a.corpus else ROOT / "corpus" / "chunks"
    ddir = Path(a.corpus) if a.corpus else ROOT / "corpus" / "metadata"
    ar = jl(cdir / "chunks_ar.jsonl")
    fr = jl(cdir / "chunks_fr.jsonl")
    docs = {}
    for lg in ("fr", "ar"):
        d = json.loads((ddir / f"documents_{lg}.json").read_text(encoding="utf-8"))
        for x in (d if isinstance(d, list) else d.values()):
            docs[x["document_id"]] = x
    frart, frall = {}, collections.defaultdict(list)
    for c in fr:
        if "~" in c["document_id"]:
            continue
        frall[c["work_id"]].append(c["text"])
        if c.get("article"):
            frart.setdefault((c["work_id"], c["article"]), []).append(c["text"])
    ar_by = collections.defaultdict(list)
    for c in ar:
        ar_by[c["document_id"]].append(c)
    out, rows = {}, []
    for method in ("pdf_text", "ocr", "mixed"):
        tot = flag = glyph = 0
        why = collections.Counter()
        for did, cs in ar_by.items():
            d = docs[did]
            if d["extraction_method"] != method or d["work_id"] not in frall:
                continue
            frn = set(numbers("\n".join(frall[d["work_id"]])))
            arn = set(numbers("\n".join(c["text"] for c in cs)))
            for c in cs:
                if c["unit_kind"] != "article" or not c.get("article"):
                    continue
                ref = " ".join(frart.get((d["work_id"], c["article"]), [])) or None
                an = [x for x in unit_anomalies(c["text"], ref, frn, arn) if x.get("severity") == "critique"]
                tot += 1
                if an:
                    flag += 1
                    glyph += any(x.get("likely_cause") for x in an)
                    why.update(x["reason"] for x in an)
                    if method == "ocr":
                        rows.append({"document_id": did, "chunk_id": c["chunk_id"], "article": c["article"], "alertes": an, "ar": c["text"][:400], "fr": (ref or "")[:400]})
        out[method] = {"articles_compares": tot, "alertes_critiques": flag, "taux": round(flag / max(1, tot), 3), "raisons": dict(why), "dont_symbole_pourcent_identifie": glyph}
    random.seed(a.seed)
    sample = random.sample(rows, min(a.n, len(rows)))
    dst = ROOT / "agent_fr" / "eval" / "results" / "ocr_alert_audit.json"
    dst.write_text(json.dumps({"corpus": a.corpus or "corpus vivant", "taux": out, "echantillon_graine": a.seed, "echantillon": sample}, ensure_ascii=False, indent=1), encoding="utf-8")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    for s in sample:
        t = s["alertes"][0]["token"]
        m = re.search(r".{0,60}" + re.escape(t.split()[0]) + r".{0,30}", s["ar"].replace("\n", " "))
        print("==", s["chunk_id"], [(x["token"], x["reason"][6:]) for x in s["alertes"]][:3], "|", (m.group(0) if m else s["ar"][:80]))
    print("écrit :", dst)


if __name__ == "__main__":
    main()
