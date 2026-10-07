"""OCR_UNCERTAIN : détection (jamais correction) des valeurs numériques suspectes d'un texte arabe issu de l'OCR.

Principe : une valeur réglementaire fausse présentée comme certaine (« 902.75 % » pour « 2,75 % ») est pire qu'une valeur signalée incertaine. Le texte OCR n'est JAMAIS modifié ni
« normalisé » ; on ajoute seulement une alerte sur l'unité (article) concernée, avec la raison et, quand il existe, la valeur du jumeau français à titre de comparaison.

Règles (comparaison article par article avec le texte français du MÊME texte juridique, sinon contrôles internes seulement) :
  R-OCR-ABSENT-JUMEAU : décimal / pourcentage / montant / nombre à ≥ 3 chiffres du texte arabe ABSENT du texte français (ex. « 902.75 » face à « 2,75 »)  -> OCR_UNCERTAIN
  R-OCR-MANQUANT      : décimal / pourcentage / montant du texte français ABSENT du texte arabe (la valeur a été perdue par l'OCR)                               -> OCR_UNCERTAIN
  R-OCR-SYMBOLE       : symbole « % » suivi d'une lettre parasite (« %o ») ou chiffres arabes-indiens collés à une valeur latine (« 2,50 ١ »)                    -> OCR_UNCERTAIN
  R-OCR-TAUX          : pourcentage > 100 (taux réglementaire implausible)                                                                                         -> OCR_UNCERTAIN
Les chiffres écrits en toutes lettres en arabe ne sont pas comparés (un nombre absent des chiffres arabes n'est signalé que si l'arabe contient au moins un chiffre).
"""
import re

from .ocr_entities import _plain, amounts, norm_number, numbers, percentages

_DEC = re.compile(r"\d+\.\d+")


def _is_decimal(tok: str) -> bool:
    return bool(_DEC.fullmatch(tok))


def _hijri_year(tok: str) -> bool:
    return tok.isdigit() and 1300 <= int(tok) <= 1500


_PCT_GLYPH = re.compile(r"(?:90|00|0)(\d+\.\d+)")


def internal_anomalies(text: str) -> list[dict]:
    t = _plain(text)
    out = []
    for m in re.finditer(r"[%٪]\s*[A-Za-z]\b", t):
        out.append({"token": m.group(0), "reason": "R-OCR-SYMBOLE", "severity": "critique", "detail": "symbole % suivi d'une lettre parasite"})
    for m in re.finditer(r"\d[.,]\d+\s+[٠-٩]", text or ""):
        out.append({"token": m.group(0), "reason": "R-OCR-SYMBOLE", "severity": "critique", "detail": "chiffre arabe-indien collé à une valeur décimale"})
    for p in percentages(text):
        try:
            if float(p) > 100:
                out.append({"token": p + " %", "reason": "R-OCR-TAUX", "severity": "critique", "detail": "taux supérieur à 100 %"})
        except ValueError:
            pass
    return out


def compare_with_french(ar_text: str, fr_text: str, fr_doc_nums: set | None = None, ar_doc_nums: set | None = None) -> list[dict]:
    """`fr_doc_nums` / `ar_doc_nums` : nombres de TOUT le texte français / arabe. Une valeur absente de l'article français correspondant mais présente ailleurs dans le texte français est un
    défaut d'alignement des articles (numérotation OCR), pas une erreur de chiffre : elle n'est pas signalée."""
    ar_nums, fr_nums = numbers(ar_text), set(numbers(fr_text))
    if not ar_nums:
        return []                                                  # arabe sans chiffre (nombres en lettres) : rien à comparer
    ar_set = set(ar_nums)
    sensitive_ar = set(percentages(ar_text)) | set(amounts(ar_text)) | {n for n in ar_set if _is_decimal(n) or (n.isdigit() and len(n) >= 3 and not _hijri_year(n))}
    pct_fr = set(percentages(fr_text)) | set(amounts(fr_text))              # valeurs (taux, montants) que le texte arabe DOIT porter ; les décimales nues du français sont presque toujours des numéros de paragraphe (« 1.1 », « 4.2 »)
    sensitive_fr = pct_fr - {n for n in fr_nums if _hijri_year(n)}
    out = []
    pct_ar = set(percentages(ar_text)) | set(amounts(ar_text))
    for n in sorted(sensitive_ar - fr_nums):
        if fr_doc_nums is not None and n in fr_doc_nums:
            continue
        a = {"token": n, "reason": "R-OCR-ABSENT-JUMEAU", "detail": "valeur absente du texte français", "expected_in_french": sorted(sensitive_fr - ar_set)[:4],
             # valeur de TAUX / montant / décimale = critique ; entier de 3 chiffres ou plus (année, numéro de référence) = information (jamais d'avertissement dans la réponse)
             "severity": "critique" if n in pct_ar else "info"}
        m = _PCT_GLYPH.fullmatch(n) or re.fullmatch(r"(?:9|0)?(?:6|9|0)0?(\d+\.\d+)", n)
        if m and m.group(1) in pct_fr:                              # « 902.75 », « 960.25 », « 00.25 » : le symbole % lu comme des chiffres devant la valeur (cause la plus fréquente, mesurée)
            a["likely_cause"] = "R-OCR-PCT-GLYPH : symbole % probablement lu comme des chiffres (« 90 », « 96 », « 00 »…)"
            a["value_in_french_text"] = m.group(1)                  # indice pour le relecteur ; la valeur arabe n'est PAS remplacée
            a["severity"] = "critique"
        out.append(a)
    for n in sorted(sensitive_fr - ar_set):
        if ar_doc_nums is not None and n in ar_doc_nums:
            continue
        out.append({"token": n, "reason": "R-OCR-MANQUANT", "severity": "critique", "detail": "valeur du texte français non retrouvée dans le texte arabe"})
    return out


def unit_anomalies(ar_unit_text: str, fr_unit_text: str | None, fr_doc_nums: set | None = None, ar_doc_nums: set | None = None) -> list[dict]:
    out = internal_anomalies(ar_unit_text)
    if fr_unit_text:
        seen = {(a["token"], a["reason"]) for a in out}
        out += [a for a in compare_with_french(ar_unit_text, fr_unit_text, fr_doc_nums, ar_doc_nums) if (a["token"], a["reason"]) not in seen]
    return out


def annotate_document(ar_doc: dict, fr_doc: dict | None) -> dict:
    """Ajoute `ocr_uncertain` (liste d'anomalies) à chaque unité du document arabe issu de l'OCR et retourne un résumé. `_units` : unités de structure (build.py)."""
    fr_by_num = {}
    fr_doc_nums = ar_doc_nums = None
    if fr_doc:
        for u in fr_doc.get("_units", []):
            if u["kind"] == "article" and u["number"] and u["number"] not in fr_by_num:
                fr_by_num[u["number"]] = u["text"]
        fr_doc_nums = set(numbers("\n".join(u["text"] for u in fr_doc.get("_units", []))))
        ar_doc_nums = set(numbers("\n".join(u["text"] for u in ar_doc.get("_units", []))))
    n_units = n_flag = n_tw = 0
    for u in ar_doc.get("_units", []):
        text = u["text"]
        ref = fr_by_num.get(u["number"]) if u["kind"] == "article" and u["number"] else None
        an = unit_anomalies(text, ref, fr_doc_nums, ar_doc_nums)     # préambule / annexes : contrôles internes seulement (pas de correspondance d'unité)
        u["ocr_uncertain"] = [a for a in an if a.get("severity") == "critique"]      # alerte (réponse, interface) : valeurs critiques seulement
        u["ocr_numeric_notes"] = [a for a in an if a.get("severity") != "critique"]  # entiers non corroborés (années, références) : conservés pour la relecture, sans alerte
        an = u["ocr_uncertain"]
        n_units += 1
        n_flag += 1 if an else 0
        n_tw += 1 if ref else 0
    return {"units": n_units, "units_flagged": n_flag, "units_compared_with_french": n_tw, "french_twin": bool(fr_doc)}
