"""Tests des garde-fous de la couche d'accès (local_app/grounding.py) : normalisation de la saisie et retrait d'une définition non soutenue par les textes retrouvés.
Cas d'origine (18 octobre 2026) : « C’est quoi l’allocation touristique ? » recevait une définition fausse, assemblée à partir de textes sur le rapatriement d'une dépouille.
Lancer : python local_app/tests/test_grounding.py   (affiche « Tests garde-fous : X/Y »)."""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_app import grounding as G                   # noqa: E402
from local_app import service as S                     # noqa: E402
from local_app.server import create_app                # noqa: E402
from local_app.tests import fakes                      # noqa: E402

PORT = 8796
BASE = f"http://127.0.0.1:{PORT}"
os.environ["AGENT_LLM"] = "local"

DEATH_TEXT = ("Règlement n°91-06 du 16 mai 1991 fixant les conditions d’attribution d’allocations en devises à l’occasion d’hospitalisation et/ou de décès de nationaux à l’étranger. "
              "En cas de décès à l'étranger d'un national résidant en voyage touristique ou d'affaires, une allocation en devises pour le rapatriement de la dépouille mortelle est délivrée.")
TRAVEL_TEXT = "Instruction n° 07-2026 du 13 juillet 2026 relative au droit de change pour voyage à l’étranger. Le montant annuel maximum du droit de change pour voyage à l'étranger est fixé à 750 euros."


def test_typographic_characters_are_brought_back_to_ascii():
    assert G.normalise_question("C’est quoi l’allocation touristique ?") == "C'est quoi l'allocation touristique ?"
    assert G.normalise_question("c‘est quoi  lʼallocation​ ?") == "c'est quoi l'allocation ?"
    assert G.normalise_question("  Quel   est le plafond d`indemnisation ?  ") == "Quel est le plafond d'indemnisation ?"
    ascii_only = "Quel est le plafond d'indemnisation par déposant ?"
    assert G.normalise_question(ascii_only) == ascii_only                                      # une saisie déjà normale n'est pas touchée
    assert G.normalise_question("« Règlement 2020-03 » — article 5") == "« Règlement 2020-03 » — article 5"      # guillemets et tirets conservés


def test_definition_questions_give_their_term():
    cases = {
        "C’est quoi l’allocation touristique ?": "allocation touristique", "c'est quoi l'allocation touristique?": "allocation touristique",
        "Qu'est-ce que l'allocation touristique ?": "allocation touristique", "Qu'est-ce qu'un prestataire de services de paiement ?": "prestataire de services de paiement",
        "qu est ce que le Salam": "salam", "Définition du droit de change": "droit de change", "Définition de la monnaie électronique": "monnaie électronique",
        "Que signifie agrément ?": "agrément", "Que veut dire plafond d'indemnisation ?": "plafond d'indemnisation", "Explique-moi le fixing": "fixing",
        "l'allocation touristique c'est quoi ?": "allocation touristique", "C'est quoi le droit de change pour voyage à l'étranger ?": "droit de change pour voyage à l'étranger",
    }
    for q, shown in cases.items():
        d = G.definition_term(q)
        assert d is not None and d[0].lower().replace("é", "e") == shown.lower().replace("é", "e"), (q, d)


def test_other_questions_are_never_treated_as_definitions():
    for q in ("Quel est le montant de l'allocation touristique ?", "Quel est le plafond d'indemnisation par déposant ?", "Que dit l'article 5 du règlement 20-03 ?",
              "Qu'est-ce que prévoit l'article 5 ?", "Qu'est-ce que la banque doit déclarer ?", "Qu'est-ce que le règlement 24-02 ?", "Explique-moi l'article 12",
              "C'est quoi la différence entre les deux ?", "Qui peut ouvrir un compte devises ?", "allocation touristique", "Bonjour", "", "Définition",
              "Qu'est-ce que le taux de change appliqué en 2020 ?", "Qu'est-ce que la mise en place du dispositif de contrôle interne des banques et des établissements financiers ?"):
        assert G.definition_term(q) is None, q


def test_term_must_appear_in_the_retrieved_texts():
    assert G.unsupported_term("C’est quoi l’allocation touristique ?", [DEATH_TEXT]) == "allocation touristique"            # le cas d'origine : « touristique » et « allocation » sont là, mais séparés
    assert G.unsupported_term("Qu'est-ce que l'allocation touristique ?", [DEATH_TEXT, TRAVEL_TEXT]) == "allocation touristique"
    assert G.unsupported_term("C'est quoi le droit de change pour voyage à l'étranger ?", [TRAVEL_TEXT]) is None              # le terme figure tel quel
    assert G.unsupported_term("C'est quoi le droit de change pour voyage ?", [TRAVEL_TEXT]) is None                          # …ou avec un mot outil en moins
    assert G.unsupported_term("Qu'est-ce que le droit de change ?", [TRAVEL_TEXT]) is None
    assert G.unsupported_term("C'est quoi les allocations en devises ?", [DEATH_TEXT]) is None                               # pluriel / singulier
    assert G.unsupported_term("C'est quoi le rapatriement de la dépouille mortelle ?", [DEATH_TEXT]) is None                 # accents et casse indifférents
    assert G.unsupported_term("C'est quoi l'ALLOCATION en DEVISES ?", [DEATH_TEXT]) is None
    assert G.unsupported_term("C'est quoi le plafond d'indemnisation ?", ["Le plafond d’indemnisation par déposant est fixé"]) is None
    assert G.unsupported_term("C'est quoi le rapatriement touristique ?", [DEATH_TEXT]) == "rapatriement touristique"          # mots présents mais pas ensemble
    assert G.unsupported_term("Quel est le montant de l'allocation touristique ?", [DEATH_TEXT]) is None                      # hors portée : pas une demande de définition
    assert G.unsupported_term("C'est quoi l'allocation touristique ?", [None, "", DEATH_TEXT]) == "allocation touristique"    # valeurs vides tolérées


def _service():
    state = {"online": True}
    agent = fakes.make_agent(state=state)
    svc = S.Service(agent=agent, llm_probe=lambda: {"online": True, "model": "m", "model_matches": True}, smalltalk_llm=lambda q, st: None)
    svc.warm_up()
    return svc, create_app(svc, PORT).test_client(), agent


def test_service_withdraws_an_unsupported_definition_and_says_why():
    _, c, agent = _service()
    r = c.post("/api/chat", json={"question": "C’est quoi l’allocation touristique ?"}, base_url=BASE)
    d = r.get_json()
    assert r.status_code == 200 and d["status"] == "refused" and d["found"] is False and d["reason"] == "terme_absent", d
    assert "« allocation touristique » n'apparaît dans aucun des textes retrouvés" in d["answer"]
    assert d["sources"] == [] and d["citations"] == [] and d["texts"] == [] and d["texts_intro"] is None and d["notes"] == []
    assert "dépouille" not in str(d) and "50.000" not in str(d)                                    # rien du texte faux ne subsiste dans la réponse
    assert d["question"] == "C’est quoi l’allocation touristique ?"                                # la question affichée est celle de la personne
    assert agent.calls[-1][0] == "C'est quoi l'allocation touristique ?"                           # le moteur reçoit la saisie normalisée


def test_service_keeps_a_supported_definition_and_other_questions_untouched():
    _, c, agent = _service()
    d = c.post("/api/chat", json={"question": "C'est quoi le plafond d'indemnisation par déposant ?"}, base_url=BASE).get_json()
    assert d["status"] == "answered" and d["found"] is True and len(d["sources"]) == 2, d["status"]
    d = c.post("/api/chat", json={"question": "Quel est le montant de l'allocation touristique ?"}, base_url=BASE).get_json()
    assert d["status"] == "answered", "hors de la portée du garde-fou : transmis tel quel"
    assert agent.calls[-1][0] == "Quel est le montant de l'allocation touristique ?"                # saisie ASCII : transmise sans aucune retouche


def test_guard_is_logged_without_the_question_text():
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="guard_log_"))
    S.setup_logging(d / "api.log")
    try:
        _, c, _ = _service()
        c.post("/api/chat", json={"question": "C'est quoi l'allocation touristique ?"}, base_url=BASE)
        for h in list(S.LOG.handlers):
            h.flush()
        txt = (d / "api.log").read_text(encoding="utf-8")
        assert '"event": "guard"' in txt and "terme_absent" in txt and "touristique" not in txt
    finally:
        for h in list(S.LOG.handlers):
            S.LOG.removeHandler(h)
            h.close()


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
    print(f"\nTests garde-fous : {len(TESTS) - len(failed)}/{len(TESTS)}")
    sys.exit(1 if failed else 0)
