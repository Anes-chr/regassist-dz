"""Pilote : compare des réglages d'OCR arabe sur un échantillon de pages, avec le jumeau français comme référence INDIRECTE des chiffres.
Mesure par variante : confiance Tesseract, part de lettres arabes, rappel des nombres (≥ 2 chiffres) du texte français correspondant, temps par page.
Aucun résultat n'est copié dans le corpus : c'est un outil de décision (faut-il changer la chaîne OCR ?).
Usage : python -m agent_fr.eval.human.ocr_pilot [--docs 14] [--pages 2] [--seed 3]"""
import argparse
import io
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ocr(img, lang, psm=None, tessdata=None):
    import pytesseract
    cfg = f"--psm {psm}" if psm else ""
    if tessdata:
        cfg += f' --tessdata-dir "{tessdata}"'
    d = pytesseract.image_to_data(img, lang=lang, config=cfg, output_type=pytesseract.Output.DICT)
    words = [w for w in d["text"] if w.strip()]
    confs = [float(c) for c, w in zip(d["conf"], d["text"]) if w.strip() and float(c) >= 0]
    return " ".join(words), (sum(confs) / len(confs) if confs else 0.0)


def prep(img, mode):
    from PIL import ImageOps
    g = img.convert("L")
    if mode == "gris":
        return g
    if mode == "otsu":
        import numpy as np
        a = np.asarray(g)
        hist, _ = np.histogram(a, bins=256, range=(0, 256))
        tot, sumB, wB, best, thr = a.size, 0.0, 0, 0.0, 128
        s = float((hist * np.arange(256)).sum())
        for t in range(256):
            wB += hist[t]
            if wB == 0:
                continue
            wF = tot - wB
            if wF == 0:
                break
            sumB += t * hist[t]
            mB, mF = sumB / wB, (s - sumB) / wF
            var = wB * wF * (mB - mF) ** 2
            if var > best:
                best, thr = var, t
        return g.point(lambda p: 255 if p > thr else 0)
    return ImageOps.autocontrast(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=14)
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    import fitz
    from PIL import Image
    from boa_pipeline import extract as X
    X._ocr_available()
    snap = Path("D:/llm/snapshots/corpus_2026-10-06")
    ar = json.loads((snap / "documents_ar.json").read_text(encoding="utf-8"))
    ar = ar if isinstance(ar, list) else list(ar.values())
    frch = {}
    for l in open(snap / "chunks_fr.jsonl", encoding="utf-8"):
        c = json.loads(l)
        if "~" not in c["document_id"]:
            frch.setdefault(c["work_id"], []).append(c["text"])
    cands = [d for d in ar if d.get("extraction_method") == "ocr" and d["work_id"] in frch and d.get("page_count", 0) >= 3]
    random.Random(a.seed).shuffle(cands)
    sample = cands[:a.docs]
    variants = {
        "courant (400 dpi, ara+fra, psm auto)": dict(dpi=400, lang="ara+fra", psm=None, mode=None),
        "ara seul (400 dpi)": dict(dpi=400, lang="ara", psm=None, mode=None),
        "300 dpi, ara+fra": dict(dpi=300, lang="ara+fra", psm=None, mode=None),
        "400 dpi + binarisation Otsu": dict(dpi=400, lang="ara+fra", psm=None, mode="otsu"),
        "400 dpi, psm 6 (bloc uniforme)": dict(dpi=400, lang="ara+fra", psm=6, mode=None),
        "500 dpi, ara+fra": dict(dpi=500, lang="ara+fra", psm=None, mode=None),
    }
    acc = {k: {"conf": [], "ar": [], "rappel": [], "t": []} for k in variants}
    for d in sample:
        p = Path(d["raw_path"]) if Path(d["raw_path"]).is_absolute() else ROOT / "corpus" / d["raw_path"]
        if not p.exists():
            p = ROOT / d["raw_path"]
        fr_nums = set(re.findall(r"\d{2,}", " ".join(frch[d["work_id"]])))
        doc = fitz.open(p)
        for pi in range(min(a.pages, doc.page_count)):
            page = doc[pi]
            for name, v in variants.items():
                t0 = time.time()
                pix = page.get_pixmap(dpi=v["dpi"])
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                if v["mode"]:
                    img = prep(img, v["mode"])
                txt, conf = ocr(img, v["lang"], v["psm"])
                txt = X.normalize_chars(txt)
                nums = set(re.findall(r"\d{2,}", txt.translate(INDIC)))
                ns = re.sub(r"[\s\d]", "", txt)
                acc[name]["conf"].append(conf)
                acc[name]["ar"].append(sum(1 for ch in ns if "\u0600" <= ch <= "\u06FF") / max(1, len(ns)))
                acc[name]["rappel"].append(len(nums & fr_nums) / max(1, len(nums)))     # précision des nombres lus : part de ceux qui existent dans le texte français
                acc[name]["t"].append(time.time() - t0)
        doc.close()
    print(f"{len(sample)} documents, {a.pages} pages chacun")
    for k, v in acc.items():
        print(f"{k:42} conf {statistics.mean(v['conf']):5.1f} | lettres arabes {statistics.mean(v['ar']):.3f} | nombres confirmés par le FR {statistics.mean(v['rappel']):.3f} | {statistics.mean(v['t']):.1f} s/page")
    out = {k: {m: round(statistics.mean(x), 3) for m, x in v.items()} for k, v in acc.items()}
    (ROOT / "agent_fr" / "eval" / "results" / "ocr_pilot.json").write_text(json.dumps({"docs": [d["work_id"] for d in sample], "pages": a.pages, "variantes": out}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
