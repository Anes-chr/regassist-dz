"""Détection des références explicites dans une question : « règlement n° 14-02 », « article 5 », années."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from boa_pipeline.relations import num_key  # noqa: E402  (tolérance 14-02 / 2014-02)

TYPE_WORDS = {
    "reglement": "REG", "règlement": "REG", "instruction": "INS", "loi": "LOI", "ordonnance": "ORD",
    "decret": "DEC", "décret": "DEC", "decision": "DCS", "décision": "DCS", "note": "NOT", "circulaire": "CIR",
    "lignes directrices": "LD", "ligne directrice": "LD",
}
REF = re.compile(r"(r[èe]glement|instruction|loi|ordonnance|d[ée]cret|d[ée]cision|note|circulaire|lignes?\s+directrices?)"
                 r"\s+(?:\w+\s+)?n\s*[°ºo]?\s*[°º]?\s*[:.]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4}(?:\s*[-/–]\s*\d{1,4})?)", re.I)
REF_NUM_ONLY = re.compile(r"\bn\s*[°º]\s*(\d{1,4}\s*[-/–]\s*\d{1,4})", re.I)
ART = re.compile(r"\barticles?\s+(?:n\s*[°º]\s*)?(\d{1,3}|premier|1er)(?:\s*(bis|ter|quater))?", re.I)
YEAR = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")


def parse_question(q: str) -> dict:
    out = {"refs": [], "articles": [], "years": [int(y) for y in YEAR.findall(q)]}
    for m in REF.finditer(q):
        t = m.group(1).lower()
        t = re.sub(r"\s+", " ", t)
        code = TYPE_WORDS.get(t) or TYPE_WORDS.get(t.replace("é", "e").replace("è", "e")) or (
            "LD" if t.startswith("ligne") else None)
        number = re.sub(r"\s+", "", m.group(2).replace("–", "-").replace("/", "-"))
        out["refs"].append({"type_code": code, "number": number, "key": num_key(number)})
    if not out["refs"]:
        for m in REF_NUM_ONLY.finditer(q):
            number = re.sub(r"\s+", "", m.group(1).replace("–", "-").replace("/", "-"))
            out["refs"].append({"type_code": None, "number": number, "key": num_key(number)})
    for m in ART.finditer(q):
        n = m.group(1).lower()
        n = "1" if n in ("premier", "1er") else n
        out["articles"].append(n + (f" {m.group(2).lower()}" if m.group(2) else ""))
    return out
