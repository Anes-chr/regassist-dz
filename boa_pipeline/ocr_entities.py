"""Entités juridiques CRITIQUES d'un texte (français ou arabe) : chiffres, pourcentages, montants, dates, numéros d'articles, numéros de textes, noms propres, termes juridiques.
Sert (1) au benchmark OCR (comparer deux moteurs sur ce qui compte juridiquement, pas sur le taux de caractères) et (2) à la détection `OCR_UNCERTAIN` (comparer un texte arabe issu de
l'OCR à son jumeau français). Aucune valeur n'est jamais corrigée ni normalisée dans le corpus : ces fonctions ne font que LIRE et comparer."""
import re
import unicodedata

from .classify import AR_MONTHS, MONTHS, ar_norm

INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# chiffres éventuellement COLLÉS à des lettres arabes (« جزائري2 000 000دج », fréquent dans les PDF arabes) : seules les bornes numériques comptent
_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d{1,3}(?:\.\d{3})+(?![\d])|\d+(?:[.,]\d+)?)(?!\d)")
_PCT = re.compile(r"(?:(\d+(?:[.,]\d+)?)[ 	]*[%٪]|[%٪][ 	]*(\d+(?:[.,]\d+)?))")      # même ligne uniquement : la couche texte arabe met parfois « % » seul sur sa ligne
_UNIT = re.compile(r"(?<![A-Za-z])(?:DA|D\.A|dinars?|milliards?|millions?)(?![A-Za-z])|(?<![؀-ۿ])(?:دج|د\.ج|دينار|دنانير|مليار|ملايير|مليون|ملايين)(?![؀-ۿ])", re.I)
FR_DATE = re.compile(r"(?<!\w)(1\s*er|premier|\d{1,2})\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+(\d{4})", re.I)
AR_DAY = r"(\d{1,2}|الفاتح|الاول|الأول|غرة)"
AR_DATE = re.compile(AR_DAY + r"\s*(" + "|".join(sorted(AR_MONTHS, key=len, reverse=True)) + r")\s*(?:سنة\s*|عام\s*)?(\d{4})")
FR_ARTICLE = re.compile(r"(?m)^\s*Article\s+(\d+|premier|1\s*er)\b", re.I)
AR_ARTICLE = re.compile(r"(?m)^\s*(?:المادة|مادة)\s+(\d+)")
FR_TEXTNUM = re.compile(r"n\s*[°º]\s*(\d{1,4}\s*[-/–]\s*\d{1,4})", re.I)
AR_TEXTNUM = re.compile(r"رقم\s*[:]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4})")
NAME_AFTER = re.compile(r"(?:المحافظ|محافظ(?:\s+بالنيابة)?)\s+((?:[ء-ي]+\s+){1,3}[ء-ي]+)")
LEGAL_TERMS = ["المادة", "النظام", "التعليمة", "البنوك", "المؤسسات المالية", "بنك الجزائر", "الاحتياطيات الإجبارية", "معدل", "الفائدة", "رأس", "الحد الأدنى", "القرض",
               "الودائع", "التعويض", "الترخيص", "العملة الصعبة", "التوطين", "الصادرات", "الواردات", "الجريدة الرسمية", "يحدد", "تعدل", "تتمم", "تلغى", "المحافظ",
               "مجلس النقد والقرض", "الزبائن", "الحسابات", "التصريح", "العمليات", "الشروط", "الأموال الخاصة"]


def norm_digits(s: str) -> str:
    return (s or "").translate(INDIC)


def _plain(s: str) -> str:
    return norm_digits(ar_norm(s or ""))


def norm_number(tok: str) -> str:
    """'2 000 000' -> '2000000' ; '2.000.000' -> '2000000' ; '2,75' -> '2.75' ; '902.75' -> '902.75'. Lecture seule : sert à COMPARER, jamais à réécrire le texte."""
    t = tok.replace(" ", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ ]\d{3})+(?:[.,]\d+)?", t):
        t = t.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t):
        t = t.replace(".", "")
    return t.replace(",", ".")


def numbers(text: str) -> list[str]:
    return [norm_number(m.group(1)) for m in _NUM.finditer(_plain(text))]


def percentages(text: str) -> list[str]:
    return [norm_number(a or b) for a, b in _PCT.findall(_plain(text))]


def amounts(text: str) -> list[str]:
    t = _plain(text)
    out = []
    for m in _NUM.finditer(t):
        around = t[max(0, m.start() - 12): m.end() + 22]
        if _UNIT.search(around):
            out.append(norm_number(m.group(1)))
    return out


def dates(text: str, lang: str) -> list[tuple]:
    """Dates grégoriennes (année, mois, jour). Les dates hégiriennes (noms de mois hégiriens) ne sont pas reconnues : elles ne sont pas comparées."""
    t = _plain(text)
    out = []
    if lang == "fr":
        for d, mon, y in FR_DATE.findall(t):
            mm = MONTHS.get(mon.lower().replace("û", "u").replace("é", "e").replace("è", "e")) or MONTHS.get(mon.lower())
            if mm:
                out.append((int(y), mm, 1 if d.lower().replace(" ", "") in ("1er", "premier") else int(d)))
    else:
        for d, mon, y in AR_DATE.findall(t):
            out.append((int(y), AR_MONTHS[mon], 1 if not d.isdigit() else int(d)))
    return out


def article_numbers(text: str, lang: str) -> list[str]:
    t = _plain(text)
    rx = FR_ARTICLE if lang == "fr" else AR_ARTICLE
    return ["1" if m.lower().replace(" ", "") in ("premier", "1er") else m for m in rx.findall(t)]


def text_numbers(text: str, lang: str) -> list[tuple]:
    """Numéros de textes cités (« n° 25-07 », « رقم 07-25 ») : paire non ordonnée de nombres à 2 chiffres (l'arabe écrit parfois l'année d'abord, parfois le numéro)."""
    t = _plain(text)
    rx = FR_TEXTNUM if lang == "fr" else AR_TEXTNUM
    out = []
    for m in rx.findall(t):
        parts = [p.strip() for p in re.split(r"[-/–]", m)]
        out.append(tuple(sorted(p[-2:] if len(p) == 4 else p.zfill(2) for p in parts)))
    return out


def proper_names(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", m).strip() for m in NAME_AFTER.findall(_plain(text))]


def legal_terms(text: str) -> set[str]:
    t = re.sub(r"\s+", " ", _plain(text))
    return {w for w in LEGAL_TERMS if w in t}


def entity_sets(text: str, lang: str) -> dict:
    return {"chiffres": set(numbers(text)), "pourcentages": set(percentages(text)), "montants": set(amounts(text)), "dates": set(dates(text, lang)),
            "articles": set(article_numbers(text, lang)), "numeros_de_textes": set(text_numbers(text, lang)), "noms_propres": set(proper_names(text)), "termes_juridiques": legal_terms(text)}
