"""Étapes 13-14 : contrôles qualité par document + rapports de couverture."""
import re
from collections import Counter

from . import config as C

NORMATIVE_NEEDS_ARTICLES = {"REG", "LOI", "ORD", "DEC"}   # les instructions/notes n'ont souvent pas d'articles


def _art_int(n):
    m = re.match(r"^(\d+)$", (n or "").strip())
    return int(m.group(1)) if m else None


def numbering_issues(units: list) -> list[str]:
    nums = [u["number"] for u in units if u["kind"] == "article" and not u.get("annexe")]
    base = [_art_int(n) for n in nums]
    issues = []
    ints = [n for n in base if n is not None]
    if not ints:
        return issues
    dup = [n for n, c in Counter(ints).items() if c > 1]
    if dup:
        issues.append(f"articles_dupliques:{dup[:10]}")
    uniq = sorted(set(ints))
    gaps = [n for n in range(uniq[0], uniq[-1] + 1) if n not in set(uniq)]
    if gaps:
        issues.append(f"articles_manquants:{gaps[:15]}")
    if uniq[0] != 1:
        issues.append(f"premier_article={uniq[0]}")
    if ints != sorted(ints):
        issues.append("ordre_non_croissant")
    return issues


def check_document(d: dict) -> dict:
    """Renvoie {'flags': [...], 'severity': 'ok|review|failed', 'details': {...}} ; modifie d['quality_flags']."""
    flags, det = list(d.get("quality_flags", [])), {}
    ex = d["extraction"]
    text = d.get("_full_text", "")
    chars = len(text.strip())
    pages = ex["pages"]
    n_pages = max(len(pages), 1)
    failed = False
    if ex.get("errors") and not chars:
        flags.append("extraction_en_erreur"); failed = True
    if chars == 0:
        flags.append("document_vide"); failed = True
    elif chars < 300:
        flags.append("texte_anormalement_court")
    if chars and chars / n_pages < C.LOW_TEXT_AVG_CHARS:
        flags.append("peu_de_texte_par_page")
    if chars:
        non_space = re.sub(r"\s", "", text)
        letters = sum(ch.isalpha() for ch in non_space)
        digits = sum(ch.isdigit() for ch in non_space)
        weird = 1 - (letters + digits) / max(len(non_space), 1)
        det["non_alnum_ratio"] = round(weird, 3)
        if weird > C.MAX_NONALPHA_RATIO:
            flags.append("taux_anormal_caracteres_non_alphabetiques")
        repl = text.count("�")
        if repl:
            flags.append("caracteres_illisibles"); det["replacement_chars"] = repl
    empty_pages = [p["page"] for p in pages if p["method"] == "empty" or (not p.get("chars") and p["method"] != "blank")]
    if empty_pages:
        flags.append("pages_sans_texte"); det["empty_pages"] = empty_pages[:50]
    ocr_pages = [p for p in pages if p["method"] == "ocr"]
    if ocr_pages:
        flags.append("ocr_utilise_verification_humaine"); det["ocr_pages"] = [p["page"] for p in ocr_pages]
        confs = [p["ocr_confidence"] for p in ocr_pages if p.get("ocr_confidence") is not None]
        if confs:
            det["ocr_mean_confidence"] = round(sum(confs) / len(confs), 1)
            if det["ocr_mean_confidence"] < C.OCR_LOW_CONF:
                flags.append("ocr_faible_confiance")
    st = d["structure_info"]
    if d["type_code"] in NORMATIVE_NEEDS_ARTICLES and not st["structure_detected"] and chars:
        flags.append("aucun_article_detecte")
    if st["structure_detected"]:
        ni = numbering_issues(d["_units"])
        flags += ["numerotation:" + i for i in ni]
    missing = [k for k in ("document_type", "number", "date") if not d.get(k) or d.get(k) == "autre"]
    if d["type_code"] in ("COM", "AVI") or d["type_code"] == "OTH":
        missing = [k for k in missing if k != "number"]
    if missing:
        d["missing_metadata"] = missing
        flags.append("metadonnees_incompletes:" + ",".join(missing))
    if d["language"] == "ar" and ex["method"] != "ocr":
        # PyMuPDF restitue en général l'ordre logique ; on signale tout de même si formes de présentation résiduelles
        if re.search(r"[ﭐ-﷿ﹰ-﻿]", text):
            flags.append("arabe_formes_de_presentation_residuelles")
    if d["status"] == "STATUT À VÉRIFIER":
        pass  # état normal, non bloquant (cf. champ status)
    review_flags = [f for f in flags if not f.startswith(("texte_identique", "meme_texte_plusieurs_fichiers"))]   # doublons : informatif
    severity = "failed" if failed else ("review" if review_flags else "ok")
    d["quality_flags"] = flags
    d["needs_manual_review"] = severity != "ok"
    return {"flags": flags, "severity": severity, "details": det}
