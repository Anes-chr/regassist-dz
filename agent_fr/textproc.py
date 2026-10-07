"""Normalisation / tokenisation française pour la recherche (jamais appliquée au texte affiché)."""
import re
import unicodedata

try:
    import snowballstemmer
    _STEM = snowballstemmer.stemmer("french").stemWord
except ImportError:  # repli minimal : retrait des pluriels
    def _STEM(w):
        return w[:-1] if len(w) > 3 and w[-1] in "sx" else w

STOP = set("""
a au aux avec ce ces dans de des du elle en et eux il ils je la le les leur lui ma mais me meme mes moi mon ne nos notre nous
on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous c d j l m n s t y ete etre est sont
etait ont avoir a-t-il quel quelle quels quelles quoi comment combien quand ou doit doivent peut peuvent faut
ci cet cette ceux celle celui entre vers sous sans aussi tout tous toute toutes plus moins tres si donc or ni car
selon lorsque alors apres avant afin dont cadre ainsi notamment present presente
""".split())


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(text: str) -> list[str]:
    t = strip_accents((text or "").lower().replace("’", "'"))
    out = []
    for w in re.findall(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", t):
        if w in STOP or len(w) < 2 and not w.isdigit():
            continue
        if re.fullmatch(r"\d+[-/]\d+(?:[-/]\d+)*", w):   # numéros « 14-02 » : gardés tels quels + éclatés
            out.append(w)
            out.extend(p for p in re.split(r"[-/]", w) if p)
            continue
        if w.isdigit():
            out.append(w)
        else:
            out.append(_STEM(w))
    return out
