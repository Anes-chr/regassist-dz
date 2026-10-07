"""Classification : type, numéro, date, langue, catégorie — à partir du libellé officiel du lien,
du nom de fichier et (plus tard) du texte. Rien n'est déduit sans indice ; sinon None."""
import re
import unicodedata
from urllib.parse import unquote, urlsplit

MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
AR_MONTHS = {"جانفي": 1, "يناير": 1, "فيفري": 2, "فبراير": 2, "مارس": 3, "أفريل": 4, "أبريل": 4, "ماي": 5, "مايو": 5,
             "جوان": 6, "يونيو": 6, "جويلية": 7, "يوليو": 7, "أوت": 8, "أغسطس": 8, "سبتمبر": 9, "أكتوبر": 10,
             "نوفمبر": 11, "ديسمبر": 12}

# (code, regex FR, regex AR)
TYPES = [
    ("LOI", r"^\s*(la\s+)?loi(\s+organique)?\b", r"^\s*(ال)?قانون"),
    ("ORD", r"^\s*(l['’]\s*)?ordonnance\b", r"^\s*(ال)?أمر"),
    ("DEC", r"^\s*(le\s+)?d[ée]cret\b", r"^\s*(ال)?مرسوم"),
    ("LD", r"^\s*(les\s+)?lignes?\s+directrices?\b", r"^\s*(ال)?مبادئ\s+توجيهية"),
    ("REG", r"^\s*(le\s+)?r[èe]glement\b", r"^\s*(ال)?نظام"),
    ("INS", r"^\s*(l['’]\s*)?instruction\b", r"^\s*(ال)?تعليمة"),
    ("DCS", r"^\s*(la\s+)?d[ée]cision\b", r"^\s*(ال)?مقرر|^\s*(ال)?قرار"),
    ("CIR", r"^\s*(la\s+)?circulaire\b", r"^\s*(ال)?منشور"),
    ("NOT", r"^\s*(la\s+|les\s+)?notes?\b", r"^\s*(ال)?مذكرة"),
    ("AVI", r"^\s*(l['’]\s*)?avis\b", r"^\s*(ال)?إشعار|^\s*(ال)?رأي"),
    ("COM", r"^\s*(le\s+)?communiqu[ée]\b", r"^\s*(ال)?بلاغ"),
]
TYPE_LABEL = {"LOI": "loi", "ORD": "ordonnance", "DEC": "décret", "LD": "lignes_directrices", "REG": "règlement",
              "INS": "instruction", "DCS": "décision", "CIR": "circulaire", "NOT": "note", "AVI": "avis",
              "COM": "communiqué", "OTH": "autre"}
NORMATIVE = {"LOI", "ORD", "DEC", "REG", "INS", "DCS", "CIR", "LD", "NOT"}

NUM_RE = re.compile(r"n\s*[°ºo]?\s*[°º]?\s*[:.]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4}(?:\s*[-/–]\s*\d{1,4})?)", re.I)
NUM_RE_AR = re.compile(r"رقم\s*[:]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4})")
DATE_FR = re.compile(r"(?:du|en date du)?\s*(\d{1,2}|1er|premier)\s*(?:er)?\s+([a-zéûôèà]+)\s*(\d{4})", re.I)       # espace facultatif mois/année : « 19 décembre1996 » (libellé du site)
CORR_RE = re.compile(r"correspondant\s+au\s+(\d{1,2}|1er)\s*(?:er)?\s+([a-zéûôèà]+)\s*(\d{4})", re.I)


AR_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
AR_MONTHS.update({"غشت": 8, "اكتوبر": 10, "افريل": 4, "أفريل": 4, "ابريل": 4, "اوت": 8, "جانفي": 1, "فيفري": 2})


def ar_norm(s: str) -> str:
    s = re.sub(r"[ـً-ٰٟ]", "", s or "")   # tatweel + diacritiques
    return s.translate(AR_DIG)


def clean_label(s: str) -> str:
    s = unicodedata.normalize("NFC", ar_norm(s) if re.search(r"[؀-ۿ]", s or "") else (s or ""))
    s = re.sub(r"^[\s–—\-•·»«]+", "", s)
    return re.sub(r"\s+", " ", s).strip()


AR_TYPO_TYPES = [("REG", r"^\s*ظام\s+رقم"), ("INS", r"^\s*عليمة\s+رقم"), ("INS", r"^\s*(ال)?متعليمة")]


def detect_type(text: str):
    t = clean_label(text)
    for code, pat in AR_TYPO_TYPES:
        if re.search(pat, t):
            return code
    for code, fr, ar in TYPES:
        if re.search(fr, t, re.I) or re.search(ar, t):
            return code
    return None


def type_in_filename(url: str):
    fn = unquote(urlsplit(url).path.rsplit("/", 1)[-1]).lower()
    for code, pat in (("LD", r"lignes?[-_ ]directrices?|\bld[-_]"), ("REG", r"\breg|r[eè]glement"),
                      ("INS", r"instruction"), ("LOI", r"\bloi\b|^loi"), ("NOT", r"\bnote")):
        if re.search(pat, fn):
            return code
    return None


def norm_number(raw: str | None):
    if not raw:
        return None
    return re.sub(r"\s+", "", raw.replace("–", "-").replace("/", "-"))


NUM_RE_NOTE = re.compile(r"n\s*[°º]\s*:?\s*(\d{1,4}\s*/\s*(?:[A-Za-z][A-Za-z.\s]*?\s*/\s*)+\d{2,4})", re.I)
NUM_RE_SINGLE = re.compile(r"n\s*[°º]\s*:?\s*(\d{1,4})(?![\d/-])", re.I)


def parse_number(text: str):
    text = ar_norm(text or "")
    m = NUM_RE.search(text) or NUM_RE_NOTE.search(text) or NUM_RE_AR.search(text) or NUM_RE_SINGLE.search(text)
    if m and m.start() > 45:   # numéro trop loin : c'est celui d'un texte visé, pas celui du document
        return None
    return norm_number(m.group(1)) if m else None


# Jour : chiffres, ou « الفاتح / الأول / غرة » (= le 1er). Les espaces entre jour, mois et année sont FACULTATIFS : les libellés du site collent souvent le mois à l'année
# (« 23 ديسمبر2008 », « 20 فبراير1991 ») ou au jour (« 14غشت 1991 », « 14أفريل سنة 2025 ») ; avec `\s+` ces dates n'étaient pas lues (mesuré : 9 textes arabes non rattachés à leur jumeau français).
AR_DAY = r"(\d{1,2}|الفاتح|الاول|الأول|غرة)"
AR_DATE = re.compile(r"(?:الموافق|مؤرخ[ةا]?\s+في|المؤرخ[ةا]?\s+في|مؤرخ[ةا]?)\s+" + AR_DAY + r"\s*(" + "|".join(AR_MONTHS) +
                     r")\s*(?:سنة\s*|عام\s*)?(\d{4})")
AR_DATE_ANY = re.compile(AR_DAY + r"\s*(" + "|".join(AR_MONTHS) + r")\s*(?:سنة\s*|عام\s*)?(\d{4})")
AR_DAY_MONTH = re.compile(r"(?:مؤرخ[ةا]?|المؤرخ[ةا]?)\s+في\s+" + AR_DAY + r"\s*(" + "|".join(AR_MONTHS) + r")(?!\w)")


def _ar_day(tok: str) -> int:
    return 1 if not tok.isdigit() else int(tok)


def parse_date_ar(text: str):
    """Date propre d'un texte arabe : on ne regarde que le segment qui suit SON numéro (« رقم 02-04 … »), jusqu'au numéro suivant (= un AUTRE texte cité,
    ex. « يتمم النظام رقم 91-08 المؤرخ في 14 غشت 1991 »). Dans le segment, la dernière occurrence « الموافق » = date grégorienne (après la date hégirienne)."""
    t = ar_norm(text or "")
    nums = [m.start() for m in re.finditer(r"رقم", t)]
    if len(nums) >= 2:
        t = t[nums[0]:nums[1]]
    elif nums:
        t = t[nums[0]:]
    m = None
    for m in AR_DATE.finditer(t):
        pass
    m = m or AR_DATE_ANY.search(t)
    if not m or m.start() > 160:
        return None, None
    d, mon, y = _ar_day(m.group(1)), AR_MONTHS[m.group(2)], int(m.group(3))
    if 1 <= d <= 31 and 1900 <= y <= 2100:
        return f"{y:04d}-{mon:02d}-{d:02d}", m.group(0)
    return None, None


def parse_day_month_ar(text: str):
    """(jour, mois) d'un libellé arabe dont l'ANNÉE est absente (« المؤرخ في 19 يوليو »). N'est JAMAIS utilisé comme date : seulement comme indice de rattachement FR/AR, jamais seul."""
    t = ar_norm(text or "")
    nums = [m.start() for m in re.finditer("رقم", t)]
    if nums:
        t = t[nums[0]:nums[1]] if len(nums) >= 2 else t[nums[0]:]
    m = AR_DAY_MONTH.search(t)
    if not m or m.start() > 160:
        return None
    d, mon = _ar_day(m.group(1)), AR_MONTHS[m.group(2)]
    return (d, mon) if 1 <= d <= 31 else None


# « Règlement n°2002-04 du 9 janvier 2003 complétant le règlement n°91-08 du 14 août 1991 » : la date PROPRE du texte est celle qui suit SON numéro ; la seconde est celle d'un
# autre texte (mesuré : 43 documents français avec une date d'un texte cité, ex. 1991 au lieu de 2003 ; notes dont la date était celle de l'instruction 08-16, 2016-09-01).
OWN_RE = re.compile(r"(?<!\w)n\s*[°º]\s*([\w/\-–. ]{1,22}?)[\s,]+(?:(?:du|au|en date du)\s+)?(\d{1,2}|1er|premier)\s*(?:er)?\s+([a-zéûôèà]+)(?:\s*(\d{4}))?", re.I)
FIRST_NUMBER = re.compile(r"(?<!\w)n\s*[°º]", re.I)
REF_BEFORE = re.compile(r"(?:r[èe]glement|instruction|loi|ordonnance|d[ée]cret|note|d[ée]cision|circulaire)\s+n\s*[°º]?\s*[\w/\-– ]{1,20}\s*$", re.I)
YEAR_IN_NUMBER = re.compile(r"(?<!\d)((?:19|20)\d\d)(?!\d)")


def _month(mon: str):
    return MONTHS.get(mon.lower()) or MONTHS.get(unicodedata.normalize("NFD", mon.lower())[0:0] or mon.lower())


def date_is_reference(text: str, start: int) -> bool:
    """La date qui commence en `start` est-elle celle d'un AUTRE texte (« … modifiant l'instruction n°02-09 du 25 février 2009 ») ?"""
    lo = max(0, start - 45)
    m = REF_BEFORE.search(text[lo:start].rstrip() + " ")
    if not m:
        return False
    # le PREMIER « n° » du texte est le numéro propre : la date qui le suit n'est pas une référence. Insensible à la casse : « Note N°01-2026 » (majuscule) n'était pas vu comme
    # numéro propre, le « n°08-16 » cité plus bas le devenait et sa date (1er septembre 2016) était attribuée à la note (phase 4 : NOT-02-24 et NOT-01-26).
    first_n = re.search(r"(?<!\w)n\s*[°º]", text, re.I)
    own_pos = re.search(r"(?<!\w)n\s*[°º]", m.group(0), re.I)
    return not (first_n and own_pos and lo + m.start() + own_pos.start() == first_n.start())


def parse_date(text: str):
    """Retourne (iso, raw). Date PROPRE du texte (celle qui suit son numéro) ; sinon la date grégorienne annoncée après « correspondant au » ; sinon la première date
    qui n'est pas celle d'un autre texte cité."""
    if re.search(r"[؀-ۿ]{3}", text or ""):
        iso, raw = parse_date_ar(text)
        if iso:
            return iso, raw
    text = text or ""
    first = FIRST_NUMBER.search(text)
    own = OWN_RE.match(text, first.start()) if first else None   # le PREMIER « n° » est le numéro PROPRE ; les suivants visent d'autres textes (jamais d'autre ancre)
    mon_n = _month(own.group(3)) if own else None            # mois hégirien (« 26 Safar 1440 ») : None -> « correspondant au » tranche
    if own and mon_n:
        d = 1 if own.group(2).lower() in ("1er", "premier") else int(own.group(2))
        if own.group(4):
            y = int(own.group(4))
        else:                                                # « n°09-2016 du 26 octobre » : année absente, déduite du numéro (4 chiffres) si possible
            ym = YEAR_IN_NUMBER.search(own.group(1))
            y = int(ym.group(1)) if ym else None
        if y and 1 <= d <= 31 and 1900 <= y <= 2100:
            return f"{y:04d}-{mon_n:02d}-{d:02d}", own.group(0).strip()
    m = CORR_RE.search(text)
    cands = [m] if (m and not date_is_reference(text, m.start())) else [x for x in DATE_FR.finditer(text) if not date_is_reference(text, x.start())]
    for m in cands:
        d, mon, y = m.group(1), m.group(2).lower(), int(m.group(3))
        mon_n = MONTHS.get(mon) or MONTHS.get(unicodedata.normalize("NFD", mon)[0:0] or mon)
        if not mon_n:
            continue
        day = 1 if d in ("1er", "premier") else int(d)
        if 1 <= day <= 31 and 1900 <= y <= 2100:
            return f"{y:04d}-{mon_n:02d}-{day:02d}", m.group(0).strip()
    return None, None


def parse_year_from_number(num: str | None):
    if not num:
        return None
    for part in num.split("-"):
        if len(part) == 4 and part.isdigit():
            return int(part)
    return None


def detect_language(text: str, url: str = "") -> str:
    ar = len(re.findall(r"[؀-ۿ]", text or ""))
    la = len(re.findall(r"[A-Za-zÀ-ÿ]", text or ""))
    if ar + la > 20:
        r = ar / (ar + la)
        return "ar" if r > 0.6 else ("fr" if r < 0.1 else "mixed")
    fn = unquote(url).lower()
    if re.search(r"[-_ (]ar(abe)?[-_. )]|[-_]ar\.pdf|arab", fn) or re.search(r"[؀-ۿ]", fn):
        return "ar"
    if re.search(r"[-_ (]fr(ancais)?[-_. )]|[-_]fr\.pdf", fn):
        return "fr"
    return "und"


CATEGORY_MAP = [  # (regex sur slug de la page source ou intitulé de section) -> (catégorie, sous-catégorie)
    (r"lignes?-directrice", ("lignes_directrices", None)),
    (r"notes?-aux-banques", ("notes_aux_banques", None)),
    (r"loi-monnaie|loi-mon", ("loi_monetaire_et_bancaire", None)),
    (r"reglement$|reglement-\d|-reglement", ("reglements", None)),
    (r"instruction", ("instructions", None)),
]


def category_from_context(source_page: str, heading: str, anchor_type: str | None):
    slug = unquote(urlsplit(source_page).path.strip("/")).lower()
    sub = re.sub(r"^[\s–—\-•·»«]+", "", heading or "").strip() or None
    for pat, (cat, _) in CATEGORY_MAP:
        if re.search(pat, slug):
            return cat, sub
    if anchor_type:
        return TYPE_LABEL[anchor_type] + "s", sub
    return None, sub


def classify_link(url: str, anchor: str, source_page: str, heading: str):
    label = clean_label(anchor)
    t = detect_type(label)
    t_src = "label" if t else None
    if not t:
        t = type_in_filename(url)
        t_src = "filename" if t else None
    number = parse_number(label)
    iso, raw_date = parse_date(label)
    cat, sub = category_from_context(source_page, heading, t)
    return {"title": label, "type_code": t or "OTH", "type_source": t_src, "document_type": TYPE_LABEL[t or "OTH"],
            "number": number, "date": iso, "date_raw": raw_date, "category": cat, "subcategory": sub,
            "language_hint": detect_language(label, url)}
