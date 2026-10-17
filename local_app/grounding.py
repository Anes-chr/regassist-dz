"""Garde-fous de la couche d'accès autour du moteur gelé. Le moteur n'est pas modifié ; ces garde-fous ne font que (1) normaliser la saisie avant l'appel et
(2) retirer une définition que les textes retrouvés ne soutiennent pas. Ils ne créent jamais de contenu juridique : ils peuvent seulement transformer une réponse en refus.

1. normalise_question : apostrophes et espaces typographiques (clavier de téléphone, Word) ramenés aux caractères ASCII sur lesquels le moteur a été conçu et évalué.
   Constat du 18 octobre 2026 : « c'est quoi l'allocation touristique ? » (apostrophe droite) et « C’est quoi l’allocation touristique ? » (apostrophe typographique)
   donnaient des résultats différents (refus, puis réponse fausse). La forme typographique est désormais identique à sa forme ASCII pour le moteur. La CASSE (« c'est » ou
   « C'est ») change encore sa décision : sur ce terme absent du corpus il décide près d'un seuil de similarité, et le garde-fou 2 est ce qui retire la réponse fausse dans tous les cas.
2. unsupported_term : pour une question de DÉFINITION (« c'est quoi X », « qu'est-ce que X », « définition de X », « que signifie X »…), le terme X doit figurer, tel quel
   (accents, pluriels, articles tolérés), dans au moins un des textes retrouvés. Sinon la définition produite aurait été assemblée à partir de passages qui parlent d'autre chose :
   cas observé, « allocation touristique » défini par l'allocation de rapatriement d'une dépouille mortelle (le terme n'existe dans aucun texte du corpus).
   Portée volontairement étroite : seulement les formulations de définition explicites, termes de 1 à 5 mots pleins sans verbe ni pronom, sans chiffre.
"""
import re
import unicodedata

_APOS = {ord(c): "'" for c in (chr(0x2019), chr(0x2018), chr(0x02BC), chr(0x00B4), chr(0x0060), chr(0x2032), chr(0x2035))}
_SPACES = {ord(c): " " for c in (chr(0x00A0), chr(0x202F), chr(0x2007), chr(0x2009), chr(0x2002), chr(0x2003), chr(0x3000))}
_INVISIBLE = {ord(c): None for c in (chr(0x200B), chr(0x200C), chr(0x200D), chr(0x200E), chr(0x200F), chr(0xFEFF), chr(0x00AD))}

_ARTICLES = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "ce", "cette", "cet", "ces"}
_GAP = {"de", "du", "des", "d", "la", "le", "les", "l", "en", "et", "a", "au", "aux", "pour", "par", "sur", "dans"}      # mots outils tolérés à l'intérieur d'un terme
_NOT_TERM = {"est", "sont", "etait", "sera", "soit", "doit", "doivent", "peut", "peuvent", "fait", "font", "faire", "dit", "disent", "prevoit", "prevoient", "permet", "permettent",
             "faut", "il", "elle", "ils", "elles", "on", "nous", "vous", "je", "tu", "si", "quand", "ou", "comment", "pourquoi", "quel", "quelle", "quels", "quelles", "qui", "que", "quoi",
             "avec", "sans", "entre", "selon", "apres", "avant", "combien", "ai", "as", "avons", "avez", "ont"}
_LEADS = sorted([
    ("c", "est", "quoi"), ("qu", "est", "ce", "que"), ("qu", "est", "ce", "qu"), ("qu", "est", "ce"), ("que", "signifie"), ("que", "veut", "dire"), ("que", "represente"),
    ("qu", "entend", "on", "par"), ("qu", "entendez", "vous", "par"), ("definition",), ("definis",), ("definissez",), ("explique",), ("expliquez",), ("explique", "moi"),
    ("expliquez", "moi"), ("parle", "moi", "de"), ("peux", "tu", "m", "expliquer"), ("pouvez", "vous", "m", "expliquer"),
], key=len, reverse=True)
_TRAILS = [("c", "est", "quoi"), ("ca", "veut", "dire", "quoi"), ("ca", "signifie", "quoi")]
MESSAGE = ("Le terme « {term} » n'apparaît dans aucun des textes retrouvés : je ne peux pas le définir à partir du corpus, "
           "et je préfère ne pas proposer une définition construite à partir de textes qui parlent d'autre chose.")


def normalise_question(q: str) -> str:
    """Apostrophes et espaces typographiques → ASCII, caractères invisibles retirés. Une question déjà en ASCII est rendue telle quelle."""
    if not isinstance(q, str):
        return q
    q = q.translate(_INVISIBLE).translate(_SPACES).translate(_APOS)
    return re.sub(r" {2,}", " ", q).strip()


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if unicodedata.category(c) != "Mn")


def _stem(t: str) -> str:
    return t[:-1] if len(t) > 3 and t[-1] in "sx" else t


def definition_term(question: str):
    """(termes_affichés, [racines des mots pleins]) si la question est une demande de définition portant sur un terme simple, sinon None."""
    if not isinstance(question, str) or len(question) > 200:
        return None
    orig = re.findall(r"[^\W_]+", normalise_question(question).lower())
    fold = [_fold(t) for t in orig]
    start, end = 0, len(fold)
    for lead in _LEADS:
        if tuple(fold[:len(lead)]) == lead:
            start = len(lead)
            break
    else:
        for trail in _TRAILS:
            if len(fold) > len(trail) and tuple(fold[-len(trail):]) == trail:
                end = len(fold) - len(trail)
                break
        else:
            return None
    while start < end and fold[start] in _ARTICLES:
        start += 1
    term_f, term_o = fold[start:end], orig[start:end]
    content = [t for t in term_f if t not in _GAP]
    if not (1 <= len(content) <= 5) or term_f[0] in _GAP or term_f[-1] in _GAP:
        return None
    if any(t.isdigit() or t in _NOT_TERM for t in term_f):
        return None
    shown = re.sub(r"\b([dlcjmnst]) (?=\w)", r"\1'", " ".join(term_o))
    return shown, [_stem(t) for t in content]


def _contains(stems, text: str) -> bool:
    words = " ".join(_stem(t) for t in re.findall(r"[^\W_]+", _fold(text)))
    gap = "(?:" + "|".join(sorted(_GAP, key=len, reverse=True)) + ")"
    pattern = r"(?<!\S)" + (r"(?:\s+" + gap + r"){0,2}\s+").join(re.escape(s) for s in stems) + r"(?!\S)"
    return re.search(pattern, words) is not None


def unsupported_term(question: str, texts):
    """Le terme à définir (tel qu'écrit par la personne) si la question demande une définition ET que ce terme est absent de tous les textes, sinon None."""
    d = definition_term(question)
    if d is None:
        return None
    shown, stems = d
    for t in texts:
        if t and _contains(stems, t):
            return None
    return shown
