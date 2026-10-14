"""Messages de courtoisie : salutations, remerciements, au revoir, « comment vas-tu », « qui es-tu », « aide ».

Le moteur gelé traite TOUT message comme une question de recherche : « Bonjour » donnait un refus froid, et « Salam » (salutation, mais aussi contrat de finance islamique
du corpus) donnait une définition juridique. Cette étape, dans la couche d'accès et AVANT la recherche, repère ces seuls messages. Elle ne modifie pas le moteur : tout
message qui n'est pas ENTIÈREMENT composé de mots de courtoisie (ou qui contient un chiffre) est transmis au moteur tel quel.
Règle de prudence : mieux vaut laisser passer un message de courtoisie au moteur que d'avaler une vraie question.

Réponse : si le modèle local est libre, il rédige une réponse naturelle (il ne voit QUE ce message de courtoisie, jamais une question juridique) ; sa sortie est contrôlée
(accept). Sinon — file occupée, modèle éteint ou lent, sortie non conforme — un texte fixe est donné aussitôt.
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
         "toujours"}
_ALLOWED = _GREET | _HOW | _THANKS | _BYE | _GLUE
_ISLAMIC_REPLY = {"alaykum", "alaykoum", "alikoum", "aleykoum", "alaikoum", "aleikoum", "عليكم", "وعليكم"}
_TU = {"tu", "toi", "te", "vas", "es", "sais", "peux", "sers"}
_VOUS = {"vous", "allez", "etes", "savez", "pouvez", "servez"}

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

EXAMPLE = "Quel est le plafond d'indemnisation par déposant ?"
INTRO = ("Je suis un assistant éducatif non officiel qui explore les textes réglementaires publics de la Banque d'Algérie. "
         f"Posez-moi une question précise, par exemple : « {EXAMPLE} ». "
         "Mes réponses citent l'article, la page et le PDF officiel ; elles peuvent être incomplètes ou erronées et ne constituent pas un avis juridique.")
ABOUT = INTRO + " Si aucun texte ne correspond à votre question, je le dis plutôt que d'inventer une réponse."
THANKS = "Avec plaisir ! Si vous avez une autre question sur un texte réglementaire de la Banque d'Algérie, je suis là. Pensez à vérifier chaque citation dans le texte officiel (PDF)."
BYE = "Au revoir ! Pensez à vérifier dans les textes officiels (PDF) avant toute décision."
# Textes fixes de repli à la deuxième personne du singulier quand la personne tutoie (le modèle, lui, suit le registre via la consigne)
INTRO_TU = ("Je suis un assistant éducatif non officiel qui explore les textes réglementaires publics de la Banque d'Algérie. "
            f"Pose-moi une question précise, par exemple : « {EXAMPLE} ». "
            "Mes réponses citent l'article, la page et le PDF officiel ; elles peuvent être incomplètes ou erronées et ne constituent pas un avis juridique.")
ABOUT_TU = INTRO_TU + " Si aucun texte ne correspond à ta question, je le dis plutôt que d'inventer une réponse."
THANKS_TU = "Avec plaisir ! Si tu as une autre question sur un texte réglementaire de la Banque d'Algérie, je suis là. Pense à vérifier chaque citation dans le texte officiel (PDF)."
BYE_TU = "Au revoir ! Pense à vérifier dans les textes officiels (PDF) avant toute décision."
SALAM_NOTE_TU = " Si tu pensais au contrat Salam (finance islamique), précise ta question, par exemple : « Quelle est la définition du Salam ? »."
SALAM_NOTE = " Si vous pensiez au contrat Salam (finance islamique), précisez votre question, par exemple : « Quelle est la définition du Salam ? »."


# ----- Réponse naturelle par le modèle local -----
KIND_LABELS = {"greeting": "salutation", "greeting_how": "salutation suivie de « ça va ? »", "how": "« ça va ? » sans salutation", "salam": "salutation « salam » seule (ambiguë)",
               "islamic": "salutation islamique complète", "thanks": "remerciement ou compliment", "bye": "au revoir ou voeu de bonne journée",
               "about": "question sur l'assistant lui-même"}
SYSTEM_PROMPT = (
    "Tu es l'assistant d'un projet éducatif NON officiel qui aide à explorer les textes réglementaires publics de la Banque d'Algérie (règlements, instructions, notes). "
    "Tu réponds en français, de façon chaleureuse, naturelle et brève : une ou deux phrases courtes (trois au maximum pour « qui es-tu »), un seul paragraphe, sans liste, sans mise en forme, sans émoji. "
    "Le message reçu est UNIQUEMENT de la courtoisie, jamais une question juridique : ne donne AUCUNE information juridique ni aucun chiffre. "
    "Le type du message, le registre (tutoiement ou vouvoiement) et la formule d'ouverture te sont donnés : respecte-les exactement. Si une formule d'ouverture est donnée, commence ta réponse par elle. "
    f"Le SEUL exemple de question que tu peux citer est : « {EXAMPLE} ». N'invente jamais d'autre exemple. "
    "Un remerciement appelle « Avec plaisir » ou équivalent, pas « Très bien ». Réponds à « ça va ? » comme une personne polie, sans prétendre avoir une vie personnelle. "
    "Pour un au revoir, souhaite simplement une bonne suite, sans remercier pour la conversation. "
    "Si on te demande qui tu es ou ce que tu sais faire : dis que tu cherches dans les textes réglementaires publics de la Banque d'Algérie et que tu cites l'article, la page et le PDF officiel, "
    "que tu n'es pas un service officiel, que tu peux te tromper et que tu ne remplaces pas un juriste ; tu n'interprètes pas la loi et tu ne donnes pas d'avis juridique.")
_SHOTS = [
    ("salutation", "vouvoiement", "Bonjour !", "Bonjour",
     f"Bonjour ! Ravi de vous accueillir. Posez-moi une question sur un texte réglementaire de la Banque d'Algérie, par exemple : « {EXAMPLE} »"),
    ("salutation suivie de « ça va ? »", "tutoiement", "Salut !", "Salut, ça va ?",
     "Salut ! Ça va très bien, merci. Et toi ? Si tu as une question sur un texte réglementaire de la Banque d'Algérie, je t'écoute."),
    ("remerciement ou compliment", "vouvoiement", "aucune", "Merci beaucoup !",
     "Avec plaisir ! N'hésitez pas à revenir si un autre texte réglementaire vous pose question."),
    ("au revoir ou voeu de bonne journée", "vouvoiement", "aucune", "Bonne journée",
     "Bonne journée à vous aussi ! Pensez à vérifier les textes officiels (PDF) avant toute décision."),
    ("question sur l'assistant lui-même", "tutoiement", "aucune", "Qui es-tu ?",
     f"Je suis un assistant éducatif non officiel : je cherche dans les textes réglementaires publics de la Banque d'Algérie et je cite l'article, la page et le PDF officiel. "
     f"Je peux me tromper et je ne remplace pas un juriste. Pose-moi une question précise, par exemple : « {EXAMPLE} »"),
    ("salutation « salam » seule (ambiguë)", "vouvoiement", "Salam !", "Salam",
     "Salam ! Pensiez-vous au contrat Salam, en finance islamique, ou souhaitez-vous poser une autre question sur les textes de la Banque d'Algérie ?"),
]
_INTERNAL = re.compile(r"qwen|llama|rerank|embedding|\be5\b|phase|no-go|prompt|syst[èe]me gel|claude|anthropic|openai|gpt|corpus|token", re.I)
_EMOJI = re.compile("[{}-{}{}-{}{}-{}{}{}]+".format(chr(0x1F000), chr(0x1FAFF), chr(0x2600), chr(0x27BF), chr(0x2B00), chr(0x2BFF), chr(0xFE0F), chr(0x200D)))
_CJK = re.compile("[{}-{}{}-{}{}-{}]".format(chr(0x3040), chr(0x30FF), chr(0x3400), chr(0x9FFF), chr(0xAC00), chr(0xD7AF)))
_TU_WORDS = re.compile(r"\b(?:tu|toi|ton|ta|tes|te)\b|\bt['’]", re.I)
_VOUS_WORDS = re.compile(r"\b(?:vous|votre|vos)\b", re.I)
_CAVEAT = " Mes réponses peuvent contenir des erreurs : vérifiez toujours le texte officiel (PDF)."


def _fold(s: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if unicodedata.category(c) != "Mn")))


def accept(text, st):
    """Texte généré utilisable tel quel, ou None (le texte fixe sera alors utilisé). Le contrôle est volontairement strict.
    `st` = résultat de classify (type, formule d'ouverture, registre) ; une simple chaîne (type) est tolérée."""
    kind = st if isinstance(st, str) else st["kind"]
    opening = None if isinstance(st, str) else st.get("opening")
    register = None if isinstance(st, str) else st.get("register")
    if not isinstance(text, str):
        return None
    t = re.sub(r"[*`#_]+", "", text)
    t = _EMOJI.sub("", t)                                                       # le modèle en glisse parfois malgré la consigne : on les retire
    t = re.sub(r"\s*\n+\s*", " ", t)
    t = re.sub(r" {2,}", " ", t).strip()
    if t.count("«") == 1 and t.count("»") == 1 and t.startswith("«") and t.endswith("»"):
        t = t[1:-1].strip()                                                      # le texte entier était entre guillemets
    elif t.startswith('"') and t.endswith('"'):
        t = t[1:-1].strip()
    if not 2 <= len(t) <= 600:
        return None
    if re.search(r"\d|https?:|www\.|@|[<>{}\[\]\\]", t) or _CJK.search(t) or _INTERNAL.search(t):
        return None
    if opening and not _fold(t).startswith(_fold(opening)):
        return None                                                              # la formule imposée (Bonsoir, Wa alaykum salam…) doit ouvrir la réponse
    if register == "tutoiement" and _VOUS_WORDS.search(t) or register == "vouvoiement" and _TU_WORDS.search(t):
        return None                                                              # le registre de la personne doit être respecté
    if kind == "thanks" and re.match(r"\s*tr[èe]s bien", t, re.I) or kind == "bye" and re.search(r"merci pour (?:votre|la|cette|ta|ton)", t, re.I):
        return None                                                              # confusions fréquentes d'un petit modèle
    for quoted in re.findall(r"«([^»]*)»", t):
        if _fold(quoted) not in (_fold(EXAMPLE), _fold("Quelle est la définition du Salam ?")):
            return None                                                          # aucun exemple de question inventé
    if re.search(r"par exemple|\bex\s*:", t, re.I) and _fold(EXAMPLE) not in _fold(t):
        return None
    if t.count("«") != t.count("»"):
        return None
    if kind == "about" and not re.search(r"erreur|juriste|v[ée]rifi|tromp", t, re.I):
        t += _CAVEAT
    if kind == "salam" and not (re.search(r"salam", t, re.I) and re.search(r"contrat", t, re.I)):
        t += SALAM_NOTE
    return t


def generate(question: str, st, timeout=(1.5, 30.0)):
    """Réponse du modèle LOCAL (boucle locale seulement, comme tout le reste), ou None si indisponible, occupé, trop lent ou non conforme."""
    try:
        import requests
        from agent_fr import llm_backends as B

        def user(label, register, opening, message):
            return f"Type : {label}\nRegistre : {register}\nFormule d'ouverture : {opening}\nMessage reçu : {message}"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for label, reg, op, msg, reply in _SHOTS:
            messages += [{"role": "user", "content": user(label, reg, op, msg)}, {"role": "assistant", "content": reply}]
        messages.append({"role": "user", "content": user(KIND_LABELS.get(st.get("label") or st["kind"], "courtoisie"), st.get("register") or "vouvoiement", st.get("opening") or "aucune", question)})
        body = {"model": "local", "temperature": 0.6, "top_p": 0.9, "max_tokens": 110, "cache_prompt": True, "messages": messages}
        r = requests.post(B.local_url() + "/v1/chat/completions", json=body, timeout=timeout)
        r.raise_for_status()
        return accept(r.json()["choices"][0]["message"]["content"], st)
    except Exception:
        return None


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")          # accents français et signes diacritiques arabes
    text = text.replace("’", " ").replace("'", " ").replace("-", " ").replace("ـ", "")
    return " ".join(re.findall(r"[^\W\d_]+", text))


def _register(tokens) -> str:
    """Tutoiement si la personne tutoie ou emploie une formule familière (« salut », « coucou », « ça va ? »), vouvoiement sinon (par défaut, ton institutionnel)."""
    t = set(tokens)
    informal = bool(t & {"salut", "coucou", "hey", "slm"}) or {"ca", "va"} <= t
    return "tutoiement" if (t & _TU or informal) and not t & _VOUS else "vouvoiement"


def _opening(tokens, kind: str):
    """Formule d'ouverture imposée (reprise de ce que la personne a dit), ou None."""
    t = set(tokens)
    if kind == "salam":
        return "Salam !"
    if not t & _GREET:
        return None
    if t & _ISLAMIC_REPLY:
        return "Wa alaykum salam !"
    for word, out in (("bonsoir", "Bonsoir !"), ("salut", "Salut !"), ("coucou", "Coucou !")):
        if word in t:
            return out
    return "Hello !" if t & {"hello", "hi", "hey"} else "Bonjour !"


def classify(question: str):
    """None = ce n'est pas un message de courtoisie (à transmettre au moteur) ;
    sinon {"kind", "label", "reply" (texte fixe), "opening", "register"}."""
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
        reg = _register(tokens)
        return {"kind": "about", "label": "about", "reply": ABOUT_TU if reg == "tutoiement" else ABOUT, "opening": None, "register": reg}
    if not set(tokens) <= _ALLOWED:
        return None
    greet, how = set(tokens) & _GREET, set(tokens) & _HOW
    bye, thanks = set(tokens) & _BYE, set(tokens) & _THANKS
    if not (greet or how or bye or thanks):
        return None
    reg = _register(tokens)
    tu = reg == "tutoiement"
    if tokens == ["salam"]:
        return {"kind": "salam", "label": "salam", "reply": "Salam ! " + (INTRO_TU + SALAM_NOTE_TU if tu else INTRO + SALAM_NOTE), "opening": "Salam !", "register": reg}
    if greet or how:
        opening = _opening(tokens, "greeting")
        well = "Tout fonctionne de mon côté, merci. " if how else ""
        label = "islamic" if set(tokens) & _ISLAMIC_REPLY else ("greeting_how" if how and greet else "how" if how else "greeting")
        reply = ((opening + " ") if opening else "") + well + (INTRO_TU if tu else INTRO)
        return {"kind": "greeting", "label": label, "reply": reply, "opening": opening, "register": reg}
    if bye:
        return {"kind": "bye", "label": "bye", "reply": BYE_TU if tu else BYE, "opening": None, "register": reg}
    return {"kind": "thanks", "label": "thanks", "reply": THANKS_TU if tu else THANKS, "opening": None, "register": reg}
