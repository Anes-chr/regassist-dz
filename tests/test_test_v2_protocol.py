"""Phase 4 — protocole TEST v2 : prérequis, auteur humain, gel, verrou « une seule exécution ». Aucun TEST v2 réel n'existe : tout se passe dans des dossiers temporaires (FIXTURES).
Lancer : python tests/test_test_v2_protocol.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_fr.eval.human import test_v2 as T


def _items(n, author="Me Dupont, juriste", kind="humain", prefix="Question de test numéro"):
    return [{"id": f"V{i:03d}", "split": "TEST2", "type_de_question": "A_direct", "question": f"{prefix} {i} sur un sujet réglementaire distinct {i * 7}", "redaction": {"auteur": author, "type": kind}} for i in range(n)]


def _write(td, items):
    p = Path(td) / "q.jsonl"
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    return p


def test_validate_requires_a_human_author_enough_questions_and_no_reuse_of_v1_questions():
    with tempfile.TemporaryDirectory() as td:
        ok = T.validate(_write(td, _items(100)))
        assert ok["ok"] and ok["n"] == 100
        ai = T.validate(_write(td, _items(100, author="Claude (IA)", kind="ia")))
        assert not ai["ok"] and any("non humain" in e for e in ai["erreurs"])
        assert any("<" in e and "100" in e for e in T.validate(_write(td, _items(99)))["erreurs"])                      # moins de 100 questions
        v1 = json.loads((T.HERE / "benchmark_v1_draft.jsonl").read_text(encoding="utf-8").splitlines()[0])["question"]
        items = _items(100)
        items[0]["question"] = v1
        assert any("DEV / TEST v1" in e for e in T.validate(_write(td, items))["erreurs"])
        items = _items(100)
        items[1]["question"] = items[0]["question"]
        assert any("double" in e for e in T.validate(_write(td, items))["erreurs"])


def _patch(td):
    old = (T.V2, T.QUESTIONS, T.MANIFEST, T.LOCK)
    T.V2 = Path(td) / "v2"
    T.V2.mkdir()
    T.QUESTIONS, T.MANIFEST, T.LOCK = T.V2 / "q.jsonl", T.V2 / "MANIFEST.json", T.V2 / "LOCK"
    return old


def _restore(old):
    T.V2, T.QUESTIONS, T.MANIFEST, T.LOCK = old


def test_freeze_is_refused_without_confirmation_or_when_a_prerequisite_is_missing():
    with tempfile.TemporaryDirectory() as td:
        old = _patch(td)
        try:
            q = _write(td, _items(100))
            for kw, msg in (({"confirm": False, "prereq": {"_toutes_reunies_avant_gel": True}}, "confirm-no-tuning"),
                            ({"confirm": True, "prereq": {"_toutes_reunies_avant_gel": False, "3_validation_humaine": {"ok": False, "detail": "absente"}}}, "prérequis")):
                try:
                    T.freeze(q, td, **kw)
                    raise AssertionError("gel accepté à tort")
                except SystemExit as e:
                    assert msg in str(e)
            assert not T.MANIFEST.exists()
        finally:
            _restore(old)


def test_current_state_has_no_test_v2_and_human_validation_is_not_reached():
    pre = T.prerequisites()
    assert pre["3_validation_humaine"]["ok"] is False and pre["_toutes_reunies_avant_gel"] is False and not T.MANIFEST.exists() and not T.LOCK.exists()


def test_run_is_refused_without_manifest_after_a_code_change_and_after_a_first_run():
    with tempfile.TemporaryDirectory() as td:
        old = _patch(td)
        try:
            try:
                T.check_before_run()
                raise AssertionError("exécution acceptée sans manifeste")
            except SystemExit as e:
                assert "pas gelé" in str(e)
            q = _write(td, _items(3))
            T.QUESTIONS.write_bytes(q.read_bytes())
            corpus = Path(td) / "corpus"
            corpus.mkdir()
            (corpus / "chunks_fr.jsonl").write_text("{}", encoding="utf-8")
            code = Path(td) / "code.py"
            code.write_text("x = 1\n", encoding="utf-8")
            man = {"questions_sha256": T.sha(T.QUESTIONS), "code": {}, "corpus": {"dir": str(corpus), "fichiers": {"chunks_fr.jsonl": T.sha(corpus / "chunks_fr.jsonl")}}}
            T.MANIFEST.write_text(json.dumps(man), encoding="utf-8")
            assert T.check_before_run()["questions_sha256"] == man["questions_sha256"]                               # état gelé et intact : autorisé
            (corpus / "chunks_fr.jsonl").write_text("{} ", encoding="utf-8")
            try:
                T.check_before_run()
                raise AssertionError("corpus modifié accepté")
            except SystemExit as e:
                assert "corpus a changé" in str(e)
            (corpus / "chunks_fr.jsonl").write_text("{}", encoding="utf-8")
            T.QUESTIONS.write_text(T.QUESTIONS.read_text(encoding="utf-8") + "\n{}", encoding="utf-8")
            try:
                T.check_before_run()
                raise AssertionError("questions modifiées acceptées")
            except SystemExit as e:
                assert "questions ont changé" in str(e)
        finally:
            _restore(old)


def test_lock_is_written_before_the_run_and_forbids_a_second_run():
    with tempfile.TemporaryDirectory() as td:
        old = _patch(td)
        real = subprocess.run
        seen = {}
        try:
            q = _write(td, _items(2))
            T.QUESTIONS.write_bytes(q.read_bytes())
            corpus = Path(td) / "c"
            corpus.mkdir()
            T.MANIFEST.write_text(json.dumps({"questions_sha256": T.sha(T.QUESTIONS), "code": {}, "corpus": {"dir": str(corpus), "fichiers": {}}}), encoding="utf-8")

            def fake_run(cmd, **kw):
                seen["lock_exists_at_run_time"] = T.LOCK.exists()                                                  # le verrou existe AVANT l'exécution
                return subprocess.CompletedProcess(cmd, 0)
            subprocess.run = fake_run
            T.run()
            assert seen["lock_exists_at_run_time"] is True
            try:
                T.run()
                raise AssertionError("seconde exécution acceptée")
            except SystemExit as e:
                assert "déjà été exécuté" in str(e)
        finally:
            subprocess.run = real
            _restore(old)


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
