"""Audit des citations : chaque chunk est-il retrouvé, mot pour mot (hors espaces/ponctuation/casse), dans le PDF d'origine
aux pages annoncées ? Contrôle mécanique de la traçabilité (page_number / page_end), indépendant de l'extraction du pipeline.
Les documents OCR sont exclus (le texte n'est pas comparable) et listés à part."""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("’", "'"))
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in s if not unicodedata.combining(c)))


def run(lang: str = "fr", limit_docs: int | None = None):
    chunks = [json.loads(l) for l in open(ROOT / "corpus" / "chunks" / f"chunks_{lang}.jsonl", encoding="utf-8")]
    docs = {d["document_id"]: d for d in json.loads((ROOT / "corpus" / "metadata" / f"documents_{lang}.json").read_text(encoding="utf-8"))}
    by_doc = defaultdict(list)
    for c in chunks:
        by_doc[c["document_id"]].append(c)
    stats = {"chunks": 0, "ok": 0, "page_ok_but_edge_differs": 0, "not_found": 0, "ocr_skipped": 0, "no_pdf": 0}
    bad = []
    for n, (did, cs) in enumerate(sorted(by_doc.items())):
        if limit_docs and n >= limit_docs:
            break
        d = docs[did]
        if d.get("ocr_required"):
            stats["ocr_skipped"] += len(cs)
            continue
        pdf = ROOT / "corpus" / d["raw_path"]
        if not pdf.exists():
            stats["no_pdf"] += len(cs)
            continue
        doc = fitz.open(pdf)
        pages = [norm(p.get_text("text")) for p in doc]
        for c in cs:
            stats["chunks"] += 1
            t = norm(c["text"])
            if len(t) < 12:
                stats["ok"] += 1
                continue
            lo, hi = max(1, (c["page_number"] or 1)), (c["page_end"] or c["page_number"] or 1)
            window = "".join(pages[lo - 1:hi])
            head, tail = t[:50], t[-50:]
            if head in window and tail in window:
                stats["ok"] += 1
            else:
                everywhere = "".join(pages)
                if head in everywhere and tail in everywhere:
                    stats["not_found"] += 1
                    bad.append({"chunk_id": c["chunk_id"], "problem": "texte présent mais PAS aux pages annoncées",
                                "pages": [lo, hi], "document_url": c["document_url"]})
                elif head in window or tail in window:
                    stats["page_ok_but_edge_differs"] += 1       # début ou fin diffère (césure, en-tête retiré…)
                else:
                    stats["not_found"] += 1
                    bad.append({"chunk_id": c["chunk_id"], "problem": "texte introuvable dans le PDF (reformulé ? extraction ?)",
                                "pages": [lo, hi], "document_url": c["document_url"], "extrait": c["text"][:120]})
        doc.close()
    ok_total = stats["ok"] + stats["page_ok_but_edge_differs"]
    rep = {"langue": lang, **stats, "taux_page_correcte": round(ok_total / max(stats["chunks"], 1), 4), "anomalies": bad[:200]}
    out = ROOT / "corpus" / "reports" / f"citation_audit_{lang}.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep


if __name__ == "__main__":
    r = run()
    print({k: v for k, v in r.items() if k != "anomalies"})
    for a in r["anomalies"][:12]:
        print(" ", a)
