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


def _service():
    state = {"online": True}
    agent = fakes.make_agent(state=state)
    svc = S.Service(agent=agent, llm_probe=lambda: {"online": True, "model": "m", "model_matches": True})
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
    state = {"online": True}
    agent = fakes.make_agent(delay=0.8, state=state)
    svc = S.Service(agent=agent, llm_probe=lambda: {"online": True, "model": "m", "model_matches": True})
    svc.warm_up()
    c = create_app(svc, PORT).test_client()
    t = threading.Thread(target=lambda: c.post("/api/chat", json={"question": "plafond"}, base_url=BASE))
    t.start()
    import time
    time.sleep(0.2)
    assert c.post("/api/chat", json={"question": "plafond"}, base_url=BASE).status_code == 429       # la file est occupée…
    r = c.post("/api/chat", json={"question": "Merci"}, base_url=BASE)                                # …mais un merci ne l'attend pas
    assert r.status_code == 200 and r.get_json()["status"] == "smalltalk"
    t.join()


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
