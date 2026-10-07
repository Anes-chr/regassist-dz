"""Étape 7 : structure juridique (Préambule / Titre / Chapitre / Section / Article / Annexe), FR + AR.

Entrée : pages nettoyées [{'page', 'lines'}]. Sortie : arbre imbriqué + liste plate d'unités (articles, préambule, annexes)
avec chemin hiérarchique et pages source. Le texte est conservé tel quel (reflow de lignes seulement).
"""
import re

from .clean import reflow

AR_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
AR_ORD = {"الأولى": "1", "الاولى": "1", "الثانية": "2", "الثالثة": "3", "الرابعة": "4", "الخامسة": "5", "السادسة": "6",
          "السابعة": "7", "الثامنة": "8", "التاسعة": "9", "العاشرة": "10"}
ROMAN = r"(?:[IVXLC]{1,7})"
LOWER_STOP = re.compile(r"^(du|de|des|d['’]|de\s+la|susvis|pr[ée]cit|ci-|ci\s|et\b|ou\b|a\b|à\b|alin|paragraphe|point|:?\s*(?:ci))", re.I)

RX = {
    "article_fr": re.compile(r"^\s*(?:(?:ARTICLES?|Articles?)\s+|Art\.\s*)(premier|1\s*er|\d+(?:\s*(?:bis|ter|quater|quinquies|sexies))?(?:\s*-\s*\d+)?)\s*[°º]?\s*(.*)$"),
    # « المادة8. — » (chiffre COLLÉ au mot, fréquent dans les PDF arabes : 41 documents, dont REG-20-01 et REG-26-03 sans aucun article détecté) et mot vocalisé (« المادَة », « المادّة »)
    "article_ar": re.compile(r"^\s*(?:ا[ً-ْٰـ]*ل[ً-ْٰـ]*[ـ]?)?م[ً-ْٰـ]*ا[ً-ْٰـ]*د[ً-ْٰـ]*ة[ً-ْٰـ]*(?:\s+|(?=[٠-٩\d]))"
                             r"([٠-٩\d]+(?:\s*مكرر\w*)?|" + "|".join(AR_ORD) + r"|\S+?)\s*[:\-–.]?\s*(.*)$"),
    "titre": re.compile(r"^\s*(?:TITRE|Titre)\s+(" + ROMAN + r"|\d+(?:er|re|ère)?|premier|PREMIER|unique|UNIQUE)\b\s*[:.\-–—]?\s*(.*)$"),
    "chapitre": re.compile(r"^\s*(?:CHAPITRE|Chapitre)\s+(" + ROMAN + r"|\d+(?:er|re|ère)?|premier|PREMIER|unique|UNIQUE)\b\s*[:.\-–—]?\s*(.*)$"),
    "section": re.compile(r"^\s*(?:SECTION|Section)\s+(" + ROMAN + r"|\d+(?:er|re|ère)?|premi[èe]re|PREMI[ÈE]RE|unique|UNIQUE)\b\s*[:.\-–—]?\s*(.*)$"),
    "sous_section": re.compile(r"^\s*(?:SOUS[- ]SECTION|Sous[- ]section)\s+(" + ROMAN + r"|\d+(?:er|re|ère)?|premi[èe]re|unique)\b\s*[:.\-–—]?\s*(.*)$"),
    # « ANNEXE N° 1 » : le « N° » (majuscule) était lu comme la lettre d'annexe « N » (77 chunks FR) ; « الملحق رقم 1 » : « رقم » (= numéro) était lu comme le numéro (42 chunks AR).
    "annexe": re.compile(r"^\s*(?:ANNEXES?|Annexes?)\s*(?:[nN]\s*[°º]\s*)?(" + ROMAN + r"|\d+|[A-Z])?\b\s*[:.\-–—]?\s*(.*)$"),
    "roman": re.compile(r"^\s*(" + ROMAN + r")\s*[-–—.)]\s+(\S.{2,})$"),
    "titre_ar": re.compile(r"^\s*(?:الباب)\s+(\S+)\s*[:\-–.]?\s*(.*)$"),
    "chapitre_ar": re.compile(r"^\s*(?:الفصل)\s+(\S+)\s*[:\-–.]?\s*(.*)$"),
    "section_ar": re.compile(r"^\s*(?:القسم)\s+(\S+)\s*[:\-–.]?\s*(.*)$"),
    "annexe_ar": re.compile(r"^\s*(?:الملحق|ملحق)\s*(?:رقم\s*[:.]?\s*)?(\S*)\s*[:\-–.]?\s*(.*)$"),
}
LEVELS = {"titre": 1, "chapitre": 2, "section": 3, "sous_section": 4}


def _num(raw: str) -> str:
    r = raw.strip().translate(AR_DIG)
    r = re.sub(r"\s+", " ", r)
    if r.lower() in ("premier", "première", "premiere", "1 er", "1er", "1re", "1ère"):
        return "1"
    return AR_ORD.get(r, r)


def _is_heading_like(line: str) -> bool:
    s = line.strip()
    return 0 < len(s) < 110 and not s.endswith((".", ";", ",")) and (s.isupper() or s[:1].isupper() or re.search(r"[؀-ۿ]", s) is not None)


def classify_line(line: str, lang: str):
    """(kind, number, remainder) ou None."""
    s = line.strip()
    if lang in ("ar", "mixed") or re.search(r"[؀-ۿ]", s):
        for k, key in (("article", "article_ar"), ("titre", "titre_ar"), ("chapitre", "chapitre_ar"),
                       ("section", "section_ar"), ("annexe", "annexe_ar")):
            m = RX[key].match(s)
            if m:
                return k, _num(m.group(1)), m.group(2).strip()
    m = RX["article_fr"].match(s)
    if m:
        rem = m.group(2).strip()
        # « Article 5 du règlement… » en début de ligne = renvoi, pas un en-tête
        if rem and not re.match(r"^[.:\-–—(\[«\"A-ZÀ-Ý]", rem):
            return None
        if re.match(r"^[.:\-–—\s]*[\"“«]", rem):   # « Article 182 : "Sont considérées… » : citation d'un autre texte
            return None
        if re.match(r"^(du|de|des)\s", rem, re.I) and not re.match(r"^[.:\-–—]", rem):
            return None
        rem = re.sub(r"^[\s.:\-–—]+", "", rem)
        return "article", _num(m.group(1)), rem
    m = RX["roman"].match(s)
    if m and not re.match(r"^(?:[IVXLC]+)$", m.group(2)) and len(s) < 140 and (m.group(2)[:1].isupper() or m.group(2)[:1].isdigit()):
        return "section", m.group(1), m.group(2).strip()
    for k in ("sous_section", "section", "chapitre", "titre", "annexe"):
        m = RX[k].match(s)
        if m:
            if k == "annexe" and (s[:1].islower()):
                continue
            return k, _num(m.group(1) or ""), m.group(2).strip()
    return None


FORMULA = re.compile(r"^\s*(Le Pr[ée]sident de la R[ée]publique|Le Gouverneur de la Banque d['’]Alg[ée]rie|Le Premier ministre|"
                     r"Le Chef du Gouvernement|Le Conseil mon[ée]taire et bancaire)\s*,?\s*$")
VU = re.compile(r"^\s*[-–•]?\s*Vu(?!\w)")


def _formula_at(items, i) -> bool:
    if not FORMULA.match(items[i][1]):
        return False
    for _, l in items[i + 1:i + 6]:
        if l.strip():
            return bool(VU.match(l))
    return False


def merge_split_headers(items: list) -> list:
    """« Art. » / « 135. » / « — » sur des lignes séparées (mise en page 1 mot par ligne) -> une seule ligne."""
    out, i = [], 0
    while i < len(items):
        pg, l = items[i]
        if re.fullmatch(r"\s*(Art\.|Article|ARTICLE)\s*", l):
            j = i + 1
            while j < len(items) and not items[j][1].strip():
                j += 1
            if j < len(items) and re.fullmatch(r"\s*(\d+[a-z]?|premier|1er)\s*[.:]?\s*", items[j][1]):
                merged = l.strip() + " " + items[j][1].strip()
                k = j + 1
                if k < len(items) and re.fullmatch(r"\s*[—–-]\s*", items[k][1]):
                    merged += " " + items[k][1].strip(); k += 1
                out.append((pg, merged)); i = k; continue
        out.append((pg, l)); i += 1
    return out


def split_toc(items: list, lang: str):
    """Isole un sommaire/table des matières placé avant le corps (lois, codes) pour qu'il ne produise pas de faux articles.
    Critère : au moins 8 marqueurs structurels (titre/chapitre/article…) AVANT la formule d'ouverture du texte."""
    f = next((i for i in range(len(items)) if _formula_at(items, i)), None)
    if f is None or f < 20:
        return items, []
    marks = [i for i in range(f) if classify_line(items[i][1], lang) is not None]
    if len(marks) < 8:
        return items, []
    start = marks[0]
    # on garde l'intitulé (avant le 1er marqueur) et le corps (à partir de la formule)
    return items[:start] + items[f:], [l for _, l in items[start:f] if l.strip()]


def extend_heading(items: list, i: int, heading: str, lang: str):
    """Intitulé de division sur plusieurs lignes : continue tant que la ligne suivante est une suite évidente
    (majuscules après majuscules, ou minuscule initiale après un intitulé court). Retourne (heading, nouvel_i)."""
    while i + 1 < len(items):
        nxt = items[i + 1][1].strip()
        if not nxt or classify_line(nxt, lang) is not None or len(nxt) > 80:
            break
        if heading.isupper() and nxt.isupper() or (nxt[:1].islower() and len(heading) < 80 and not heading.endswith((".", ";", ":"))):
            heading += " " + nxt; i += 1
        else:
            break
    return heading, i


def parse_structure(pages: list, lang: str = "fr") -> dict:
    rtl = lang == "ar"
    items = []  # (page, line)
    for p in pages:
        for l in p["lines"]:
            items.append((p["page"], l))
    items = merge_split_headers(items)
    items, toc_lines = split_toc(items, lang)
    units = []
    ctx = {1: None, 2: None, 3: None, 4: None}
    annex = None
    cur = {"kind": "preamble", "label": "Préambule", "number": None, "heading": None, "lines": [], "pages": set(),
           "ctx": {}, "annexe": None}
    structural_seen = False

    def ctx_snapshot():
        d = {}
        for lvl, name in ((1, "titre"), (2, "chapitre"), (3, "section"), (4, "sous_section")):
            if ctx[lvl]:
                d[name] = ctx[lvl]
        return d

    def close():
        nonlocal cur
        if cur and (cur["lines"] or cur["kind"] != "preamble"):
            units.append(cur)
        cur = None

    def start(kind, number, heading, p, label):
        nonlocal cur
        cur = {"kind": kind, "label": label, "number": number, "heading": heading or None, "lines": [], "pages": {p},
               "ctx": ctx_snapshot(), "annexe": annex}

    i = 0
    while i < len(items):
        p, l = items[i]
        if not l.strip():
            if cur is not None:
                cur["lines"].append((p, ""))
            i += 1; continue
        c = classify_line(l, lang)
        if c is None:
            if cur is None:
                start("body", None, None, p, "Corps du texte")
            cur["lines"].append((p, l)); cur["pages"].add(p)
            i += 1; continue
        kind, number, rem = c
        structural_seen = True
        if kind in LEVELS:
            close()
            lvl = LEVELS[kind]
            heading = rem
            if not heading and i + 1 < len(items) and _is_heading_like(items[i + 1][1]) and classify_line(items[i + 1][1], lang) is None:
                heading = items[i + 1][1].strip(); i += 1
            if heading:
                heading, i = extend_heading(items, i, heading, lang)
            for k in range(lvl, 5):
                ctx[k] = None
            name = {"titre": "Titre", "chapitre": "Chapitre", "section": "Section", "sous_section": "Sous-section"}[kind]
            ctx[lvl] = {"number": number, "heading": heading or None, "label": f"{name} {number}".strip()}
            cur = None  # un en-tête de division n'a pas de corps propre : il alimente le chemin des articles suivants
        elif kind == "annexe":
            close()
            for k in range(1, 5):
                ctx[k] = None
            heading = rem
            if not heading and i + 1 < len(items) and _is_heading_like(items[i + 1][1]) and classify_line(items[i + 1][1], lang) is None:
                heading = items[i + 1][1].strip(); i += 1
            if heading:
                heading, i = extend_heading(items, i, heading, lang)
            annex = {"number": number or None, "heading": heading or None, "label": f"Annexe {number}".strip()}
            start("annexe", number, heading, p, annex["label"])
        else:  # article
            close()
            start("article", number, None, p, f"Article {number}")
            if rem:
                cur["lines"].append((p, rem))
        i += 1
    close()

    if not structural_seen and units:
        units[0]["kind"] = "body"; units[0]["label"] = "Corps du texte"

    out_units = []
    for u in units:
        paras = reflow(u["lines"], rtl=rtl)
        pgs = sorted(u["pages"]) or [None]
        if paras:
            pgs = [min(q["page_start"] for q in paras), max(q["page_end"] for q in paras)]
        out_units.append({
            "kind": u["kind"], "label": u["label"], "number": u["number"], "heading": u["heading"],
            "context": u["ctx"], "annexe": u["annexe"], "paragraphs": paras,
            "text": "\n".join(q["text"] for q in paras), "page_start": pgs[0], "page_end": pgs[-1],
        })
    articles = [u for u in out_units if u["kind"] == "article"]
    has_divisions = any(u["context"] for u in out_units)
    return {"toc_lines": toc_lines, "structure_detected": bool(articles) or has_divisions, "units": out_units, "article_count": len(articles),
            "annex_count": sum(1 for u in out_units if u["kind"] == "annexe")}


def nest(units: list) -> list:
    """Vue arborescente (Document → Titre → Chapitre → Section → Article / Annexes) pour documents/*.json."""
    root, stack = [], []

    def node(u):
        return {"type": u["kind"], "label": u["label"], "number": u["number"], "heading": u["heading"],
                "page_start": u["page_start"], "page_end": u["page_end"], "children": []}
    pre = [u for u in units if u["kind"] in ("preamble", "body")]
    for u in pre:
        root.append(node(u))
    path_cache = {}
    for u in units:
        if u["kind"] in ("preamble", "body"):
            continue
        if u["kind"] == "annexe":
            nd = node(u); root.append(nd)
            path_cache[(("annexe", u["label"], u["heading"]),)] = nd
            continue
        parent = root
        keys = []
        if u["annexe"] and u["kind"] != "annexe":
            keys.append(("annexe", u["annexe"]["label"], u["annexe"].get("heading")))
        elif u["kind"] != "annexe":
            for lvl in ("titre", "chapitre", "section", "sous_section"):
                c = u["context"].get(lvl)
                if c:
                    keys.append((lvl, c["label"], c.get("heading")))
        for k in keys:
            key = tuple(keys[:keys.index(k) + 1])
            if key not in path_cache:
                nd = {"type": k[0], "label": k[1], "number": None, "heading": k[2], "children": []}
                parent.append(nd); path_cache[key] = nd
            parent = path_cache[key]["children"]
        parent.append(node(u))
    return root
