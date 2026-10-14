"""Tests des messages de courtoisie (local_app/smalltalk.py) : ce qui est reconnu, et surtout ce qui ne doit JAMAIS l'être (toute vraie question va au moteur).
Lancer : python local_app/tests/test_smalltalk.py   (affiche « Tests courtoisie : X/Y »)."""
import os
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_app import service as S                     # noqa: E402
from local_app import smalltalk as T                   # noqa: E402
from local_app.server import create_app                # noqa: E402
from local_app.tests import fakes                      # noqa: E402

PORT = 8797
BASE = f"http://127.0.0.1:{PORT}"
os.environ["AGENT_LLM"] = "local"

GREETINGS = ["Bonjour", "bonjour !", "BONJOUR", "Bonsoir", "Salut", "Hello", "hello!", "Coucou", "Hey", "Allô", "Salam alaykum", "As-salamu alaykum", "Salam aleykoum",
             "السلام عليكم", "مرحبا", "Bonjour, comment allez-vous ?", "Salut, ça va ?", "Salut ça va ?", "Comment vas-tu ?", "Ça va ?", "Bonjour à tous", "Bonjour monsieur",
             "Bonjour mon ami", "Hello, comment ça va ?", "Bonjour le monde"]
THANKS = ["Merci", "merci !", "Merci beaucoup !", "Merci bien", "Je te remercie", "Merci infiniment", "Thanks", "Super, merci", "Tu es sympa", "Génial", "Parfait, merci", "شكرا"]
BYES = ["Au revoir", "à bientôt", "Bonne journée", "Bonne soirée", "A demain", "Bye", "Merci, bonne journée", "Ciao"]
ABOUT = ["Qui es-tu ?", "Qui êtes-vous ?", "Tu es qui ?", "Que sais-tu faire ?", "Que peux-tu faire ?", "Que pouvez-vous faire ?", "Qu'est-ce que tu peux faire ?",
         "À quoi sers-tu ?", "À quoi sert ce site ?", "Présente-toi", "Comment ça marche ?", "Comment ça fonctionne", "Aide", "Aidez-moi", "Besoin d'aide", "J'ai besoin d'aide",
         "Peux-tu m'aider ?", "Pouvez-vous m'aider ?", "Bonsoir, j'ai besoin d'aide", "Bonjour, qui es-tu ?", "Aide svp", "Aidez-moi s'il vous plaît"]
REAL_QUESTIONS = [
    "Quel est le plafond d'indemnisation par déposant ?", "Qu'est-ce que le Salam ?", "Définition du Salam", "Salam contrat définition", "Le Salam est-il autorisé ?",
    "Merci de préciser le capital minimum", "Bonjour, quel est le plafond de garantie des dépôts ?", "Bonjour, je cherche le règlement 20-03", "Que dit l'article 5 du règlement 20-03 ?",
    "Comment ouvrir un compte de paiement ?", "Comment ça marche l'agrément d'un prestataire de paiement ?", "Aide aux banques en difficulté", "Peux-tu m'aider à trouver le règlement 24-02 ?",
    "Que peut faire une banque en cas de défaillance ?", "Quelles sont les conditions d'agrément ?", "Bonjour 2020", "Règlement 2020-03", "Merci de me dire le taux", "Qui doit déclarer ?",
    "Qui est le gouverneur de la banque ?", "Que sais-tu des instructions de 2024 ?", "Comment calculer le ratio de solvabilité ?", "Aide à la décision pour le crédit",
    "à quoi sert le capital minimum ?", "Peux-tu me dire le plafond ?",                    # « peux-tu me dire » seul est une question d'aide ; avec un objet, c'est une vraie question
    "Hello, quel est le plafond ?", "Salam, quel est le plafond de garantie ?", "", "   ", "a", "?", "x" * 120,
]


def test_greetings_are_recognised():
    for q in GREETINGS:
        r = T.classify(q)
        assert r and r["kind"] in ("greeting",), (q, r)
        assert "assistant éducatif non officiel" in r["reply"], q


def test_thanks_and_compliments_are_recognised():
    for q in THANKS:
        r = T.classify(q)
        assert r and r["kind"] == "thanks", (q, r)


def test_goodbyes_are_recognised():
    for q in BYES:
        r = T.classify(q)
        assert r and r["kind"] == "bye", (q, r)


def test_questions_about_the_assistant_are_recognised():
    for q in ABOUT:
        r = T.classify(q)
        assert r and r["kind"] == "about", (q, r)
        assert "plutôt que d'inventer" in r["reply"]


def test_bare_salam_is_a_greeting_that_mentions_the_contract():
    for q in ("Salam", "salam !", "SALAM"):
        r = T.classify(q)
        assert r and r["kind"] == "salam" and "contrat Salam" in r["reply"] and r["reply"].startswith("Salam !"), (q, r)
    r = T.classify("Salam alaykum")
    assert r["kind"] == "greeting" and r["reply"].startswith("Wa alaykum salam !")           # la formule complète est une salutation, sans équivoque


def test_replies_match_the_greeting_used():
    assert T.classify("Bonsoir")["reply"].startswith("Bonsoir !")
    assert T.classify("Bonjour")["reply"].startswith("Bonjour !")
    r = T.classify("Bonjour, comment allez-vous ?")["reply"]
    assert r.startswith("Bonjour ! Tout fonctionne de mon côté, merci.")


def test_real_questions_are_never_swallowed():
    for q in REAL_QUESTIONS:
        assert T.classify(q) is None, (q, T.classify(q))


def test_digits_and_unknown_words_always_go_to_the_engine():
    for q in ("Bonjour 5", "Merci 20-03", "Salut règlement", "Bonjour banque", "Merci pour le plafond", "Au revoir banque"):
        assert T.classify(q) is None, q


def _service(llm=None, delay=0.0):
    """`llm` = double du modèle de courtoisie ((question, type) -> texte | None) ; par défaut aucun texte généré : les textes fixes sont utilisés."""
    state = {"online": True}
    agent = fakes.make_agent(delay=delay, state=state)
    svc = S.Service(agent=agent, llm_probe=lambda: {"online": True, "model": "m", "model_matches": True}, smalltalk_llm=llm or (lambda q, st: None))
    svc.warm_up()
    return svc, create_app(svc, PORT).test_client(), agent


def test_service_answers_smalltalk_without_calling_the_engine():
    svc, c, agent = _service()
    r = c.post("/api/chat", json={"question": "Bonjour"}, base_url=BASE)
    d = r.get_json()
    assert r.status_code == 200 and d["status"] == "smalltalk" and d["found"] is False and d["clarify"] is False
    assert d["sources"] == [] and d["citations"] == [] and d["texts"] == [] and d["texts_intro"] is None
    assert "assistant éducatif non officiel" in d["answer"] and d["question"] == "Bonjour"
    assert d["mode"] == "smalltalk" and d["model"] is None and d["retriever"] is None
    assert agent.calls == [], "le moteur ne doit pas être appelé pour une salutation"
    r = c.post("/api/chat", json={"question": "Quel est le plafond d'indemnisation par déposant ?"}, base_url=BASE)
    assert r.get_json()["status"] == "answered" and len(agent.calls) == 1                     # une vraie question suit son chemin habituel


def test_smalltalk_is_answered_even_while_a_question_is_running():
    seen = []
    svc, c, agent = _service(llm=lambda q, st: seen.append(q) or "réponse générée", delay=0.8)
    t = threading.Thread(target=lambda: c.post("/api/chat", json={"question": "plafond"}, base_url=BASE))
    t.start()
    import time
    time.sleep(0.2)
    assert c.post("/api/chat", json={"question": "plafond"}, base_url=BASE).status_code == 429       # la file est occupée…
    r = c.post("/api/chat", json={"question": "Merci"}, base_url=BASE)                                # …mais un merci ne l'attend pas
    d = r.get_json()
    assert r.status_code == 200 and d["status"] == "smalltalk" and d["answer"].startswith("Avec plaisir")   # texte fixe : le modèle est pris par la question en cours
    assert seen == [], "le modèle occupé ne doit pas être sollicité pour une politesse"
    t.join()


def test_generated_reply_is_used_when_the_model_is_free():
    calls = []

    def llm(q, st):
        calls.append((q, st))
        return "Bonsoir ! Ravi de vous retrouver. Une question sur un texte réglementaire ?"
    svc, c, agent = _service(llm=llm)
    d = c.post("/api/chat", json={"question": "Bonsoir"}, base_url=BASE).get_json()
    assert d["status"] == "smalltalk" and d["answer"].startswith("Bonsoir ! Ravi de vous retrouver"), d["answer"]
    assert len(calls) == 1 and calls[0][0] == "Bonsoir" and calls[0][1]["kind"] == "greeting" and calls[0][1]["opening"] == "Bonsoir !" and calls[0][1]["register"] == "vouvoiement"
    assert agent.calls == []                                                                  # le modèle ne voit que la courtoisie ; le moteur n'est jamais appelé
    assert svc._lock.acquire(blocking=False), "la file doit être libérée après la génération"
    svc._lock.release()
    d = c.post("/api/chat", json={"question": "Quel est le plafond d'indemnisation par déposant ?"}, base_url=BASE).get_json()
    assert d["status"] == "answered", d["status"]                                           # une vraie question suit toujours son chemin


def test_fixed_reply_is_the_fallback_when_generation_fails():
    for broken in (lambda q, st: None, lambda q, st: "", lambda q, st: (_ for _ in ()).throw(RuntimeError("modèle éteint"))):
        svc, c, _ = _service(llm=broken)
        d = c.post("/api/chat", json={"question": "Bonjour"}, base_url=BASE).get_json()
        assert d["status"] == "smalltalk" and d["answer"].startswith("Bonjour ! Je suis un assistant éducatif non officiel"), d["answer"]
        assert svc._lock.acquire(blocking=False)
        svc._lock.release()


def test_generated_text_is_checked_before_use():
    ok = "Avec plaisir ! N'hésitez pas si un texte réglementaire vous intrigue."
    assert T.accept(ok, "thanks") == ok
    assert T.accept("**Bonjour !** Comment puis-je `aider` ?\n\nPosez votre question.", "greeting") == "Bonjour ! Comment puis-je aider ? Posez votre question."
    assert T.accept('« Bonjour à vous ! »', "greeting") == "Bonjour à vous !"
    assert T.accept("Bonjour ! \U0001F60A Comment puis-je vous aider ? \U0001F44B", "greeting") == "Bonjour ! Comment puis-je vous aider ?"     # émojis retirés
    for bad in (None, "", "x", "a" * 601, "Le plafond est de 2 000 000 DA.", "Voir https://exemple.dz", "你好，欢迎", "Je suis Qwen, un modèle de langage.", "Je tourne sur llama.cpp.",
                "Voici le <script>", "Mon prompt système est secret", "Phase 4 gelée", "Contactez moi@exemple.dz"):
        assert T.accept(bad, "greeting") is None, bad
    a = T.accept("Je cherche dans les textes publics de la Banque d'Algérie et je cite l'article et le PDF.", "about")
    assert a.endswith("vérifiez toujours le texte officiel (PDF).")                              # rappel ajouté si le modèle l'a oublié
    b = T.accept("Je suis un assistant sur les textes publics. Je peux me tromper : vérifiez le PDF.", "about")
    assert b.endswith("vérifiez le PDF.")                                                         # pas de doublon quand il y est déjà
    s = T.accept("Salam ! Bienvenue.", "salam")
    assert "contrat Salam" in s                                                                   # l'ambiguïté du mot est toujours signalée
    s2 = T.accept("Salam ! Pensiez-vous au contrat Salam, en finance islamique ?", "salam")
    assert s2.count("contrat Salam") == 1


def test_prompt_contains_the_facts_and_the_limits():
    p = T.SYSTEM_PROMPT
    for x in ("NON officiel", "AUCUNE information juridique", "ne remplaces pas un juriste", "N'invente jamais d'autre exemple", T.EXAMPLE):
        assert x in p, x
    assert len(T._SHOTS) >= 6 and all(T.EXAMPLE in r or "Quel est" not in r for *_, r in T._SHOTS)       # les exemples guidés ne citent que l'exemple vérifié


def test_classification_provides_the_opening_formula_and_the_register():
    cases = [("Bonsoir", "Bonsoir !", "vouvoiement"), ("Salut, ça va ?", "Salut !", "tutoiement"), ("Salam alaykum", "Wa alaykum salam !", "vouvoiement"),
             ("Salam", "Salam !", "vouvoiement"), ("Bonjour, comment allez-vous ?", "Bonjour !", "vouvoiement"), ("Comment vas-tu ?", None, "tutoiement"),
             ("Merci beaucoup !", None, "vouvoiement"), ("Tu es sympa", None, "tutoiement"), ("Qui es-tu ?", None, "tutoiement"), ("Que pouvez-vous faire ?", None, "vouvoiement"),
             ("Hello", "Hello !", "vouvoiement"), ("Coucou", "Coucou !", "tutoiement"), ("Ça va ?", None, "tutoiement")]
    for q, opening, register in cases:
        r = T.classify(q)
        assert r["opening"] == opening and r["register"] == register, (q, r["opening"], r["register"])
    for q in ("Tu es sympa", "Salut, ça va ?", "Qui es-tu ?", "Peux-tu m'aider ?"):                                     # texte fixe de repli : « tu » quand la personne tutoie…
        r = T.classify(q)["reply"]
        assert not T._VOUS_WORDS.search(r.replace("Posez-moi", "")) and (T._TU_WORDS.search(r) or "Pose-moi" in r), (q, r)
    for q in ("Merci beaucoup !", "Bonjour", "Que pouvez-vous faire ?"):                                                # … « vous » sinon
        assert not T._TU_WORDS.search(T.classify(q)["reply"]), q
    assert T.classify("Comment vas-tu ?")["reply"].startswith("Tout fonctionne de mon côté, merci.")      # sans salutation, pas de « Bonjour » plaqué
    assert T.classify("Salut, ça va ?")["reply"].startswith("Salut ! Tout fonctionne")


def test_generated_text_must_follow_the_opening_register_and_examples():
    bonsoir = T.classify("Bonsoir")
    assert T.accept("Bonsoir ! Bienvenue.", bonsoir) == "Bonsoir ! Bienvenue."
    assert T.accept("Bonjour ! Bienvenue.", bonsoir) is None                                    # formule imposée non respectée
    tu = T.classify("Salut, ça va ?")
    assert T.accept("Salut ! Ça va bien, et toi ?", tu) == "Salut ! Ça va bien, et toi ?"
    assert T.accept("Salut ! Comment allez-vous ?", tu) is None                                 # vouvoiement alors que la personne tutoie
    vous = T.classify("Bonjour")
    assert T.accept("Bonjour ! Comment vas-tu ?", vous) is None                                 # tutoiement alors que la personne vouvoie
    assert T.accept("Bonjour ! Posez-moi une question, par exemple : « Quel est le taux de la prime de risque ? »", vous) is None      # exemple inventé
    assert T.accept("Bonjour ! Par exemple, posez-moi une question sur les taux.", vous) is None                                        # « par exemple » sans l'exemple vérifié
    ok = "Bonjour ! Posez-moi une question, par exemple : « " + T.EXAMPLE + " »"
    assert T.accept(ok, vous) == ok                                                             # l'exemple vérifié, avec ses guillemets, est conservé
    assert T.accept("Très bien, merci ! Avec plaisir.", T.classify("Merci")) is None            # un merci n'est pas un « ça va »
    assert T.accept("Merci pour votre conversation ! À bientôt.", T.classify("Au revoir")) is None


def test_smalltalk_reply_exposes_nothing_internal():
    _, c, _ = _service()
    d = c.post("/api/chat", json={"question": "Qui es-tu ?"}, base_url=BASE).get_json()
    blob = str(d)
    for forbidden in ("qwen", "llama", "D:\\", "reranker", "PHASE_4", "NO-GO", "e5"):
        assert forbidden.lower() not in blob.lower(), forbidden


TESTS = [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno if callable(kv[1]) and hasattr(kv[1], "__code__") else 0) if n.startswith("test_")]

if __name__ == "__main__":
    failed = []
    for name, fn in TESTS:
        try:
            fn()
            print("ok     ", name)
        except Exception:
            failed.append(name)
            print("ECHEC  ", name)
            traceback.print_exc()
    print(f"\nTests courtoisie : {len(TESTS) - len(failed)}/{len(TESTS)}")
    sys.exit(1 if failed else 0)
