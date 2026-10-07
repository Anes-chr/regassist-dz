"""Étapes 5-6 : extraction PDF (texte natif), détection des pages scannées, OCR, DOCX/XLSX.

Sortie : {"method": ..., "pages": [{"page": n, "text": str, "method": "pdf_text|ocr|empty", "ocr_confidence": float|None,
          "chars": int, "tables": [md]}], "errors": [...], "page_count": n}
Le texte n'est PAS nettoyé ici (voir clean.py).
"""
import io
import re
import shutil
import unicodedata
from pathlib import Path

from . import config as C

_OCR_READY = None


def _ocr_available():
    global _OCR_READY
    if _OCR_READY is None:
        try:
            import pytesseract
            if not shutil.which("tesseract"):
                for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",):
                    if Path(p).exists():
                        pytesseract.pytesseract.tesseract_cmd = p
            pytesseract.get_tesseract_version()
            _OCR_READY = True
        except Exception:
            _OCR_READY = False
    return _OCR_READY


def ocr_lang(lang_hint: str) -> str:
    return {"ar": "ara+fra", "mixed": "fra+ara"}.get(lang_hint, "fra")


def ocr_page(page, lang: str):
    import fitz
    import pytesseract
    from PIL import Image
    pix = page.get_pixmap(dpi=C.OCR_DPI_AR if "ara" in lang else C.OCR_DPI)   # arabe : 400 dpi (meilleure confiance mesurée)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    d = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    lines, confs, cur, key = [], [], [], None
    for i, w in enumerate(d["text"]):
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
    return "\n".join(lines), (sum(confs) / len(confs) if confs else None)


def normalize_chars(text: str) -> str:
    """Normalisations techniques sans effet sur le sens : formes de présentation arabes (NFKC ciblé),
    espaces insécables, césures conditionnelles, caractères de largeur nulle."""
    out = []
    for ch in text:
        o = ord(ch)
        if 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
            out.append(unicodedata.normalize("NFKC", ch))
        else:
            out.append(ch)
    t = "".join(out)
    t = t.replace("\u00a0", " ").replace("\u202f", " ").replace("\u00ad", "")
    t = re.sub(r"[\u200b\u200c\ufeff]", "", t)
    return t


CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ue000-\uf8ff\ufffd]")
AR_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")


def _ratios(txt: str):
    ns = re.sub(r"[\s\d]", "", txt)
    if not ns:
        return 0.0, 1.0
    return len(CTRL_RE.findall(ns)) / len(ns), len(AR_RE.findall(ns)) / len(ns)


def lam_alef_inversion(txt: str):
    """Part des mots arabes commençant par « امل » (ordre inversé) parmi ceux commençant par « الم » ou « امل » ; None si trop peu de mots.
    Mesuré (oct. 2026) : 222 passages de 23 textes arabes de 2025-2026 (PDF natifs) écrivent « املصرفية » pour « المصرفية » : la recherche lexicale ne les retrouve pas."""
    inv = len(re.findall(r"(?<![\u0600-\u06FF])امل", txt))
    ok = len(re.findall(r"(?<![\u0600-\u06FF])الم", txt))
    return inv / (inv + ok) if inv + ok >= 2 else None


def text_layer_garbled(txt: str, lang_hint: str) -> bool:
    """Couche texte d'un PDF « natif » inutilisable (police sans table ToUnicode : lettres arabes remplacées par des caractères de contrôle ou ASCII).
    Mesuré sur le corpus (oct. 2026) : 20 documents arabes « pdf_text », 107 passages avec < 60 % de lettres arabes, alors que l'OCR n'en produit presque jamais."""
    ns = re.sub(r"[\s\d]", "", txt)
    if len(ns) < 80:
        return False
    ctrl, ar = _ratios(txt)
    if lang_hint in ("ar", "mixed") and (lam_alef_inversion(txt) or 0) > 0.5:
        return True
    return ctrl > 0.03 or (lang_hint == "ar" and ar < 0.6)


def extract_pdf(path: Path, lang_hint: str = "und") -> dict:
    import fitz
    res = {"method": "pdf_text", "pages": [], "errors": [], "page_count": 0, "ocr_pages": 0,
           "encrypted": False, "metadata": {}}
    try:
        doc = fitz.open(path)
    except Exception as e:
        res["errors"].append(f"ouverture impossible: {e}"); return res
    if doc.needs_pass:
        res["encrypted"] = True
        res["errors"].append("PDF protégé par mot de passe : non contourné"); return res
    res["page_count"] = doc.page_count
    res["metadata"] = {k: v for k, v in (doc.metadata or {}).items() if v}
    lang = ocr_lang(lang_hint)
    for i, page in enumerate(doc, 1):
        try:
            txt = page.get_text("text")  # ordre du flux de contenu : respecte les colonnes (sort=True les mélange)
        except Exception as e:
            res["errors"].append(f"p{i}: lecture texte {e}"); txt = ""
        txt = normalize_chars(txt)
        entry = {"page": i, "text": txt, "method": "pdf_text", "ocr_confidence": None, "tables": []}
        garbled = len(txt.strip()) >= C.OCR_MIN_CHARS_PER_PAGE and text_layer_garbled(txt, lang_hint) and _ocr_available()
        if garbled:
            try:                                                   # couche texte illisible : l'OCR remplace le texte SEULEMENT s'il est nettement meilleur
                otxt, conf = ocr_page(page, lang)
                otxt = normalize_chars(otxt)
                c0, a0 = _ratios(txt)
                c1, a1 = _ratios(otxt)
                inv0, inv1 = lam_alef_inversion(txt) or 0.0, lam_alef_inversion(otxt) or 0.0
                if (c1 < c0 and (c0 > 0.03 or a1 > a0 + 0.15)) or (inv0 > 0.5 and inv1 < 0.2 and c1 <= c0 + 0.01):
                    entry.update(text=otxt, method="ocr", ocr_confidence=conf, ocr_lang=lang, text_layer_garbled=True)
                    res["ocr_pages"] += 1
                    res["garbled_pages"] = res.get("garbled_pages", 0) + 1
                else:
                    entry["text_layer_suspect"] = True
            except Exception as e:
                res["errors"].append(f"p{i}: OCR (couche texte illisible) {e}")
        elif len(txt.strip()) < C.OCR_MIN_CHARS_PER_PAGE:
            has_img = bool(page.get_images(full=True)) or True  # page quasi vide : on tente l'OCR dans tous les cas
            if has_img and _ocr_available():
                try:
                    otxt, conf = ocr_page(page, lang)
                    otxt = normalize_chars(otxt)
                    if len(otxt.strip()) > len(txt.strip()):
                        entry.update(text=otxt, method="ocr", ocr_confidence=conf, ocr_lang=lang)
                        res["ocr_pages"] += 1
                    elif not otxt.strip():
                        entry["method"] = "empty" if page.get_images() else "blank"   # page réellement blanche ≠ échec
                except Exception as e:
                    res["errors"].append(f"p{i}: OCR {e}"); entry["method"] = "empty"
            elif not txt.strip():
                entry["method"] = "empty"
                if not _ocr_available():
                    res["errors"].append(f"p{i}: page sans texte et OCR indisponible")
        else:
            try:  # tableaux : copie markdown supplémentaire ; le texte reste la référence
                for t in page.find_tables().tables[:10]:
                    md = t.to_markdown()
                    if md and len(md) > 20:
                        entry["tables"].append(md)
            except Exception:
                pass
        res["pages"].append(entry)
    doc.close()
    n_ocr = sum(1 for p in res["pages"] if p["method"] == "ocr")
    n_txt = sum(1 for p in res["pages"] if p["method"] == "pdf_text")
    res["method"] = "ocr" if n_ocr and not n_txt else ("mixed" if n_ocr else "pdf_text")
    return res


def extract_docx(path: Path) -> dict:
    import docx
    res = {"method": "docx", "pages": [], "errors": [], "page_count": 1}
    d = docx.Document(str(path))
    lines = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    res["pages"].append({"page": 1, "text": normalize_chars("\n".join(lines)), "method": "docx",
                         "ocr_confidence": None, "tables": []})
    return res


def extract_xlsx(path: Path) -> dict:
    import openpyxl
    res = {"method": "xlsx", "pages": [], "errors": [], "page_count": 0}
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for i, ws in enumerate(wb.worksheets, 1):
        rows = ["\t".join("" if v is None else str(v) for v in r) for r in ws.iter_rows(values_only=True)]
        res["pages"].append({"page": i, "text": f"[Feuille: {ws.title}]\n" + "\n".join(rows),
                             "method": "xlsx", "ocr_confidence": None, "tables": []})
    res["page_count"] = len(res["pages"])
    return res


def extract(path: Path, ext: str, lang_hint: str = "und") -> dict:
    try:
        if ext == "pdf":
            return extract_pdf(path, lang_hint)
        if ext == "docx":
            return extract_docx(path)
        if ext in ("xlsx", "xlsm"):
            return extract_xlsx(path)
    except Exception as e:
        return {"method": ext, "pages": [], "errors": [f"échec extraction: {e}"], "page_count": 0}
    return {"method": ext, "pages": [], "errors": [f"format .{ext} non pris en charge automatiquement"], "page_count": 0,
            "unsupported": True}
