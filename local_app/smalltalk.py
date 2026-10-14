"""Messages de courtoisie : salutations, remerciements, au revoir, « comment vas-tu », « qui es-tu », « aide ».

Le moteur gelé traite TOUT message comme une question de recherche : « Bonjour » donnait un refus froid, et « Salam » (salutation, mais aussi contrat de finance islamique
du corpus) donnait une définition juridique. Cette étape, dans la couche d'accès et AVANT la recherche, répond à ces seuls messages par un texte fixe. Elle ne modifie
pas le moteur : tout message qui n'est pas ENTIÈREMENT composé de mots de courtoisie (ou qui contient un chiffre) est transmis au moteur tel quel.
Règle de prudence : mieux vaut laisser passer un message de courtoisie au moteur que d'avaler une vraie question.
"""
import re
import unicodedata

MAX_CHARS = 80
MAX_TOKENS = 8

_GREET = {
    "bonjour", "bonsoir", "salut", "coucou", "hello", "hi", "hey", "allo", "slm", "marhaba", "ahlan", "sbah",
    "salam", "salem", "salamu", "salamou", "assalam", "assalamu", "assalamou", "essalam", "aslama", "as", "alaykum", "alaykoum", "alikoum", "aleykoum", "alaikoum", "aleikoum", "wa", "wal",
    "السلام", "سلام", "عليكم", "وعليكم", "ورحمة", "الله", "وبركاته", "مرحبا", "اهلا", "هلا", "وسهلا", "صباح", "مساء", "الخير", "النور",
}
_HOW = {"va", "vas", "allez"}                                                   # « ça va », « comment vas-tu », « comment allez-vous »
_THANKS = {"merci", "remercie", "remercions", "remerciements", "thanks", "thank", "thx", "shukran", "choukran", "شكرا", "جزيلا",
           "sympa", "genial", "super", "parfait", "excellent", "bravo", "top", "cool", "nickel", "formidable"}   # remerciements et compliments
_BYE = {"revoir", "bye", "adieu", "bientot", "ciao", "tchao", "journee", "soiree", "nuit", "continuation", "demain", "weekend"}
_GLUE = {"a", "au", "tous", "tout", "toute", "le", "la", "les", "monde", "ca", "comment", "vous", "tu", "toi", "moi", "te", "je", "et", "aussi", "bien", "tres", "beaucoup",
         "mille", "infiniment", "vraiment", "encore", "cher", "chere", "monsieur", "madame", "mr", "mme", "est", "es", "etes", "suis", "vais", "bon", "bonne", "mon", "ami", "amie",
         "assistant", "bot", "robot", "l", "d", "j", "m", "s", "c", "y", "end", "week", "matin", "apres", "midi", "svp", "stp", "please", "pour", "de", "du", "un", "une",
         "toujours", "vraiment"}
_ALLOWED = _GREET | _HOW | _THANKS | _BYE | _GLUE
_ISLAMIC_REPLY = {"alaykum", "alaykoum", "alikoum", "aleykoum", "alaikoum", "aleikoum", "عليكم", "وعليكم"}

_ABOUT = [re.compile(p) for p in (
    r"^(?:qui|que) (?:es|est|etes) (?:tu|vous)(?: donc| exactement)?$",
    r"^(?:tu|vous) (?:es|etes) (?:qui|quoi)$",
    r"^(?:qu est ce que |que )?(?:tu |vous )?(?:sais|savez|peux|pouvez|sait|peut)(?: tu| vous)? (?:faire|me dire|m aider|aider)$",
    r"^(?:a quoi|pourquoi faire) (?:sers|sert|servez)(?: tu| vous)?(?: ce site| cet assistant| ce bot)?$",
    r"^(?:presente|presentez)(?: toi| vous)?(?: en quelques mots)?$",
    r"^comment (?:ca )?(?:marche|fonctionne)(?: cet assistant| ce site| ce bot| tout ca)?$",
    r"^comment (?:tu|vous) (?:fonctionnes|fonctionnez|marches|marchez)$",
    r"^(?:aide|help|aidez moi|aide moi|besoin d aide|j ai besoin d aide|peux tu m aider|pouvez vous m aider|tu peux m aider|vous pouvez m aider|puis je avoir de l aide)$",
)]
_POLITE_END = re.compile(r"(?: s il (?:vous|te) plait| svp| stp| please| merci)+$")

INTRO = ("Je suis un assistant éducatif non officiel qui explore les textes réglementaires publics de la Banque d'Algérie. "
         "Posez-moi une question précise, par exemple : « Quel est le plafond d'indemnisation par déposant ? ». "
         "Mes réponses citent l'article, la page et le PDF officiel ; elles peuvent être incomplètes ou erronées et ne constituent pas un avis juridique.")
ABOUT = INTRO + " Si aucun texte ne correspond à votre question, je le dis plutôt que d'inventer une réponse."
THANKS = "Avec plaisir ! Si vous avez une autre question sur un texte réglementaire de la Banque d'Algérie, je suis là. Pensez à vérifier chaque citation dans le texte officiel (PDF)."
BYE = "Au revoir ! Pensez à vérifier dans les textes officiels (PDF) avant toute décision."
SALAM_NOTE = " Si vous pensiez au contrat Salam (finance islamique), précisez votre question, par exemple : « Quelle est la définition du Salam ? »."


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")          # accents français et signes diacritiques arabes
    text = text.replace("’", " ").replace("'", " ").replace("-", " ").replace("ـ", "")
    return " ".join(re.findall(r"[^\W\d_]+", text))


def classify(question: str):
    """None = ce n'est pas un message de courtoisie (à transmettre au moteur) ; sinon {"kind": ..., "reply": ...}."""
    if not isinstance(question, str) or len(question) > MAX_CHARS or re.search(r"\d", question):
        return None
    text = _normalise(question)
    tokens = text.split()
    if not tokens or len(tokens) > MAX_TOKENS:
        return None
    # « Qui es-tu ? », « Que sais-tu faire ? », « Aide » : questions sur l'assistant lui-même (salutation initiale tolérée)
    core = [t for t in tokens if t not in _GREET]
    about = _POLITE_END.sub("", " ".join(core))
    if core and any(p.match(about) for p in _ABOUT):
        return {"kind": "about", "reply": ABOUT}
    if not set(tokens) <= _ALLOWED:
        return None
    greet, how = set(tokens) & _GREET, set(tokens) & _HOW
    bye, thanks = set(tokens) & _BYE, set(tokens) & _THANKS
    if not (greet or how or bye or thanks):
        return None
    if tokens == ["salam"]:
        return {"kind": "salam", "reply": "Salam ! " + INTRO + SALAM_NOTE}
    if greet or how:
        opening = "Wa alaykum salam !" if set(tokens) & _ISLAMIC_REPLY else ("Bonsoir !" if "bonsoir" in tokens else "Bonjour !")
        well = " Tout fonctionne de mon côté, merci." if how else ""
        return {"kind": "greeting", "reply": opening + well + " " + INTRO}
    if bye:
        return {"kind": "bye", "reply": BYE}
    return {"kind": "thanks", "reply": THANKS}
