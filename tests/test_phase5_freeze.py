"""Phase 5 — gel technique PHASE_4_FROZEN et interfaces de relecture. Rapides (pas de hachage des modèles) : la vérification complète se lance à la main
(`python -m agent_fr.eval.human.freeze_phase4 verify`, `... repro`). Lancer : python tests/test_phase5_freeze.py"""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_fr.eval.human import freeze_phase4 as F
from agent_fr.eval.human import review_check

BASE = {"code": {"agent_fr/retrieve2.py": {"sha256": "a"}}, "test_v1": {"x": {"sha256": "b"}}, "regles": {"bench.py": {"sha256": "c"}}, "benchmark": {}, "interfaces_et_fiches": {}, "resultats_phase4": {},
        "modeles": {"m.onnx": {"sha256": "d"}}, "index": {"vecteurs": {"v.npy": {"sha256": "e"}}},
        "corpus": {"instantane_fichiers": {"chunks_fr.jsonl": "f"}, "corpus_vivant": {"corpus/chunks/chunks_fr.jsonl": {"sha256": "f", "identique_a_l_instantane": True}},
                   "fichiers_sources_raw": {"n": 1, "empreintes_differentes_de_file_hash": [], "agregat_sha256": "g"}, "state": {"state/state.json": {"sha256": "h"}},
                   "state_extract_cache": {"fichiers": 1, "agregat_sha256": "i"}},
        "configuration": {"retrieval": {"RR_MIN": -1.9}, "embeddings": 1, "reranker": 1, "llm": 1, "prompt_systeme_sha256": "p", "refus_phrase": "r", "pipeline_corpus": 1, "ocr": 1,
                          "retriever_par_defaut": "x", "moteurs_enregistres": None},
        "versions": {"python": "3.14", "paquets": {}, "tesseract": "5.5", "llama_cpp_tag": "b1", "llama_server": []}, "ocr_uncertain_chunks_dans_l_instantane": 80}


def test_compare_is_silent_on_an_identical_state_and_ignores_documentation():
    assert F.compare(BASE, copy.deepcopy(BASE)) == {}


def test_any_change_to_engine_code_rules_configuration_or_corpus_is_an_ecart():
    cases = [("code", lambda m: m["code"]["agent_fr/retrieve2.py"].update(sha256="z")), ("code", lambda m: m["code"].update({"agent_fr/nouveau.py": {"sha256": "n"}})),            # fichier non listé = moteur modifié
             ("regles", lambda m: m["regles"]["bench.py"].update(sha256="z")), ("test_v1", lambda m: m["test_v1"]["x"].update(sha256="z")),
             ("configuration", lambda m: m["configuration"]["retrieval"].update(RR_MIN=-1.0)), ("configuration", lambda m: m["configuration"].update(prompt_systeme_sha256="q")),
             ("corpus", lambda m: m["corpus"]["corpus_vivant"]["corpus/chunks/chunks_fr.jsonl"].update(sha256="z", identique_a_l_instantane=False)),
             ("corpus", lambda m: m["corpus"]["state_extract_cache"].update(agregat_sha256="z")), ("index.vecteurs", lambda m: m["index"]["vecteurs"]["v.npy"].update(sha256="z")),
             ("modeles", lambda m: m["modeles"]["m.onnx"].update(sha256="z")), ("versions", lambda m: m["versions"].update(python="3.15")),
             ("ocr_uncertain", lambda m: m.update(ocr_uncertain_chunks_dans_l_instantane=0))]
    for group, mutate in cases:
        now = copy.deepcopy(BASE)
        mutate(now)
        diffs = F.compare(BASE, now)
        assert group in diffs, (group, diffs)


def test_create_refuses_to_rewrite_an_existing_freeze():
    with tempfile.TemporaryDirectory() as td:
        old = F.MANIFEST
        F.MANIFEST = Path(td) / "m.json"
        F.MANIFEST.write_text("{}", encoding="utf-8")
        try:
            F.create()
            raise AssertionError("réécriture acceptée")
        except SystemExit as e:
            assert "ne se réécrit pas" in str(e)
        finally:
            F.MANIFEST = old


def test_frozen_marker_and_status_are_consistent_when_the_freeze_exists():
    if not F.MANIFEST.exists():
        return                                                                       # avant le gel
    man = json.loads(F.MANIFEST.read_text(encoding="utf-8"))
    assert man["label"] == "PHASE_4_FROZEN" and man["statut_decision"] == "NO-GO PROVISOIRE" and man["raisons_du_statut"] == ["validation humaine absente", "TEST v2 absent"]
    assert hashlib.sha256(F.MANIFEST.read_bytes()).hexdigest() in F.MARKER.read_text(encoding="utf-8")
    assert man["configuration"]["ocr"]["OCR_UNCERTAIN"].startswith("actif") and "NON DÉPLOYÉ" in man["configuration"]["ocr"]["candidat_experimental"]
    assert man["ocr_uncertain_chunks_dans_l_instantane"] > 0
    for k in ("code", "test_v1", "regles", "benchmark", "interfaces_et_fiches", "resultats_phase4", "modeles"):
        assert man[k], k


def test_official_review_interfaces_pass_every_technical_check_and_are_not_regenerated():
    rep = review_check.check()
    assert rep["ok"], rep["echecs"]
    assert len(rep["controles"]) == 18


def test_ocr_pipeline_does_not_use_the_experimental_model():
    root = Path(__file__).resolve().parent.parent
    for p in list((root / "boa_pipeline").glob("*.py")) + list((root / "agent_fr").glob("*.py")):
        t = p.read_text(encoding="utf-8")
        assert "tessdata_best" not in t and "tessdata-dir" not in t, p.name                  # candidat expérimental, non déployé


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
