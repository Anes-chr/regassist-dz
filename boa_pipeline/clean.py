"""Étape 8 : nettoyage des artefacts techniques SANS toucher au sens juridique.

Retire : en-têtes/pieds répétés, numéros de page isolés, lignes d'URL parasites, espaces multiples.
Journalise tout ce qui est supprimé (cleaning_log) pour permettre l'audit.
Ne reformule pas, ne corrige pas l'orthographe, ne corrige pas l'OCR.
"""
import re
from collections import Counter

PAGENUM = re.compile(r"^\s*[-–—]?\s*(page\s*)?\d{1,3}\s*([/\-]\s*\d{1,3})?\s*[-–—]?\s*$|^\s*(صفحة)\s*\d+\s*$", re.I)
URL_LINE = re.compile(r"^\s*(https?://\S+|www\.\S+)\s*$", re.I)
EDGE = 4
STRUCT_LINE = re.compile(r"^\s*(art(icle)?s?\.?|chapitre|titre|section|annexe|المادة|مادة|الفصل|الباب|القسم|الملحق)\s*\d*", re.I)


def _sig(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip().lower()))


def clean_pages(pages: list) -> tuple[list, list]:
    """pages: [{'page', 'text', ...}] -> ([{'page', 'lines': [str], 'method', 'ocr_confidence'}], cleaning_log)"""
    log = []
    split = []
    for p in pages:
        lines = [re.sub(r"[ \t]+", " ", l).strip() for l in p["text"].split("\n")]
        lines = [l for l in lines]
        split.append(lines)
    n = len(pages)
    # en-têtes / pieds répétitifs (sur ≥ 60 % des pages, minimum 3 pages)
    rep = set()
    if n >= 3:
        cnt = Counter()
        for lines in split:
            ne = [l for l in lines if l]
            for l in set(ne[:EDGE] + ne[-EDGE:]):
                cnt[_sig(l)] += 1
        rep = {s for s, c in cnt.items() if c >= max(3, 0.6 * n) and s and len(s) < 160 and not PAGENUM.match(s)}
    out = []
    for p, lines in zip(pages, split):
        ne_idx = [i for i, l in enumerate(lines) if l]
        edge = set(ne_idx[:EDGE] + ne_idx[-EDGE:])
        kept = []
        for i, l in enumerate(lines):
            if not l:
                kept.append(""); continue
            if i in edge and PAGENUM.match(l):
                log.append({"page": p["page"], "removed": l, "why": "numéro de page"}); continue
            if i in edge and _sig(l) in rep and not STRUCT_LINE.match(l):
                log.append({"page": p["page"], "removed": l, "why": "en-tête/pied répété"}); continue
            if URL_LINE.match(l):
                log.append({"page": p["page"], "removed": l, "why": "URL isolée"}); continue
            kept.append(l)
        out.append({"page": p["page"], "lines": kept, "method": p.get("method"),
                    "ocr_confidence": p.get("ocr_confidence"), "tables": p.get("tables", [])})
    return out, log


_TERMINAL = tuple(".;:?!»)…")


def reflow(lines: list, rtl: bool = False) -> list[dict]:
    """Reconstitue les paragraphes à partir de lignes coupées artificiellement (prudent) :
    on ne joint que si la ligne précédente ne finit pas une phrase ET la suivante ne démarre pas un nouvel élément
    (numérotation, puce, majuscule). Les césures en fin de ligne sont conservées (tiret gardé).
    lines : [(page, texte)] -> [{'text', 'page_start', 'page_end'}]"""
    paras, cur = [], None
    item = re.compile(r"^\s*([-–—•·▪●]|\d+[°.)\-]|\(?[a-zA-Z]\)|\(?\d+\)|[IVX]+[.)-]|[٠-٩]+[.)-])\s")
    for pg, l in lines:
        if not l.strip():
            if cur:
                paras.append(cur); cur = None
            continue
        if cur is None:
            cur = {"text": l, "page_start": pg, "page_end": pg}; continue
        starts_new = bool(item.match(l))
        open_sentence = not cur["text"].endswith(_TERMINAL)
        cont = (not l[:1].isupper()) if not rtl else True
        if open_sentence and not starts_new and cont:
            sep = "" if re.search(r"\w-$", cur["text"]) and l[:1].islower() else " "
            cur["text"] += sep + l; cur["page_end"] = pg
        else:
            paras.append(cur); cur = {"text": l, "page_start": pg, "page_end": pg}
    if cur:
        paras.append(cur)
    return paras
