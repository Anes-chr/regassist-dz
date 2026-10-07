"""Phase 4 — enregistrement et recalcul des annotations HUMAINES : fidèle, séparé, sans modification du benchmark ni des règles. Lancer : python tests/test_human_annotations.py
Les fichiers d'annotations ci-dessous sont des FIXTURES de test (dossier temporaire) : aucune annotation humaine réelle n'existe encore."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_fr.eval.human import annotations as A


def _bench(td):
    items = [{"id": f"H{n:03d}", "type_de_question": t, "split": "TEST" if n % 2 else "DEV", "question": f"q{n}", "reponse_attendue": "r"} for n, t in
             enumerate(["A_direct", "A_direct", "C_temporelle", "G_ambigue", "A_direct", "D_modification", "A_direct", "A_direct", "C_temporelle", "A_direct"], 1)]
    p = Path(td) / "bench.jsonl"
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n", encoding="utf-8")
    return p, items


def _export(td, name, kind, verdicts, who="Me Test (fixture)"):
    p = Path(td) / name
    p.write_text(json.dumps({"kind": kind, "evaluateur": who, "exported_at": "2026-10-07T10:00:00Z", "verdicts": verdicts}, ensure_ascii=False), encoding="utf-8")
    return p


def _rev(cls, **kw):
    return {"question_ok": "oui", "source_ok": "oui", "article_ok": "oui", "reponse_ok": "oui", "date_ok": "oui", "classe": cls, **kw}


def _ans(h="non", **kw):
    return {"source": "oui", "article": "oui", "version": "oui", "reponse": "oui", "citation": "oui", "justifiee": "oui", "hallucination": h, **kw}


def test_ingest_appends_without_touching_the_benchmark_and_refuses_double_import_and_bad_values():
    with tempfile.TemporaryDirectory() as td:
        bench, _ = _bench(td)
        before = hashlib.sha256(bench.read_bytes()).hexdigest()
        ann = Path(td) / "ann"
        e = _export(td, "r.json", "benchmark_review_p4", {"H001": _rev("CORRECT"), "H002": _rev("QUESTION_MAL_FORMULEE", commentaire="ambiguë"), "H003": {"classe": "CORRECT"}})
        s = A.ingest(e, bench, ann)
        assert s["enregistrees"] == 2 and s["incompletes_ignorees"] == 1                                 # la relecture incomplète n'est jamais complétée à la place du juriste
        assert hashlib.sha256(bench.read_bytes()).hexdigest() == before                                   # benchmark intact
        try:
            A.ingest(e, bench, ann)
            raise AssertionError("double import accepté")
        except ValueError as ex:
            assert "déjà ingéré" in str(ex)
        bad = _export(td, "bad.json", "benchmark_review_p4", {"H004": _rev("PEUT-ETRE")})
        try:
            A.ingest(bad, bench, ann)
            raise AssertionError("valeur hors liste acceptée")
        except ValueError as ex:
            assert "rejetée" in str(ex)
        unk = _export(td, "unk.json", "benchmark_review_p4", {"H999": _rev("CORRECT")})
        try:
            A.ingest(unk, bench, ann)
            raise AssertionError("identifiant inconnu accepté")
        except ValueError as ex:
            assert "inconnu" in str(ex)
        anon = _export(td, "anon.json", "benchmark_review_p4", {"H005": _rev("CORRECT")}, who="")
        try:
            A.ingest(anon, bench, ann)
            raise AssertionError("annotation anonyme acceptée")
        except ValueError as ex:
            assert "évaluateur" in str(ex)
        assert len(A.load_jsonl(ann / "benchmark_review.jsonl")) == 2                                      # les refus n'ont rien écrit


def _scores(td):
    items = []
    for n in range(1, 11):
        items.append({"id": f"H{n:03d}", "doc@1": True, "article@1": True, "C3": True, "reponse_correcte": n not in (2, 6), "citation_correcte": True, "hallucination": n in (3, 5, 7)})
    p = Path(td) / "score.json"
    p.write_text(json.dumps({"items": items}), encoding="utf-8")
    return p


def test_recompute_excludes_badly_designed_questions_and_separates_hallucination_categories():
    with tempfile.TemporaryDirectory() as td:
        bench, _ = _bench(td)
        ann = Path(td) / "ann"
        rev = {f"H{n:03d}": _rev("CORRECT") for n in range(1, 11)}
        rev["H002"] = _rev("QUESTION_MAL_FORMULEE")
        rev["H004"] = _rev("AMBIGU")                                                                     # type G : « ambigu » = validation attendue, pas une exclusion
        rev["H006"] = _rev("REPONSE_ATTENDUE_INCORRECTE")
        A.ingest(_export(td, "r.json", "benchmark_review_p4", rev), bench, ann)
        ev = {"H001": _ans("non"), "H002": _ans("juridique"),                                            # H002 : question exclue -> sa « hallucination » ne compte pas
              "H003": _ans("metadonnee_interne", commentaire="date de référence de la consigne"), "H005": _ans("factuelle"), "H007": _ans("non"),
              "H006": _ans("juridique"), "H008": _ans("non", reponse="oui")}
        ev["H008"]["reponse"] = "oui"
        A.ingest(_export(td, "e.json", "human_eval_p4", ev), bench, ann)
        rep = A.recompute(bench, ann, [_scores(td)])
        v = rep["validation_benchmark"]
        assert v["items_annotes"] == 10 and set(v["questions_a_ne_pas_compter_comme_echec_du_modele"]) == {"H002", "H006"}            # H004 (type G, AMBIGU) n'est pas exclue
        e = rep["evaluation_reponses"]
        assert e["reponses_evaluees"] == 7 and e["dont_exclues_question_mal_conçue"] == 2 and e["reponses_retenues"] == 5
        h = e["hallucination_humaine"]
        assert (h["juridique"], h["factuelle"], h["metadonnee_interne_a_part"]) == (0, 1, 1)                                         # la métadonnée interne est présentée à part
        assert h["denominateur"] == 5 and h["taux_hallucination_humaine_juridique_ou_factuelle"] == 0.2
        assert h["seuils_preenregistres"] == {"hallucination_go": 0.05, "hallucination_conditional_go": 0.10, "hallucination_no_go_above": 0.10}   # le seuil n'est pas modifié
        assert "NO-GO" in h["position_par_rapport_aux_seuils"]
        sep = e["presentation_separee"]
        assert sep["metadonnee_interne"] == ["H003"] and sep["hallucination_factuelle"] == ["H005"] and sep["hallucination_juridique"] == []
        assert "H003" in sep["hallucination_automatique_non_confirmee_par_le_juriste"]                                              # auto : hallucination ; humain : métadonnée interne
        assert rep["validation_humaine_complete"]["atteinte"] is False                                                                # < 50 réponses évaluées


def test_recompute_reports_correct_answers_rejected_by_the_automatic_scoring():
    with tempfile.TemporaryDirectory() as td:
        bench, _ = _bench(td)
        ann = Path(td) / "ann"
        A.ingest(_export(td, "e.json", "human_eval_p4", {"H002": _ans("non"), "H001": _ans("non", reponse="non")}), bench, ann)
        rep = A.recompute(bench, ann, [_scores(td)])
        sep = rep["evaluation_reponses"]["presentation_separee"]
        assert sep["reponse_correcte_mais_notation_automatique_incorrecte"] == ["H002"]                  # humain : oui ; auto : non
        assert sep["reponse_incorrecte_mais_notation_automatique_correcte"] == ["H001"]


def test_recompute_on_the_real_paths_leaves_every_frozen_test_v1_file_untouched():
    """Le rapport de recalcul lit le benchmark et les notes gelées : aucune empreinte de TEST v1 ne doit changer (avec ou sans annotation)."""
    import subprocess
    cmd = [sys.executable, "-m", "agent_fr.eval.human.verify_frozen"]
    root = Path(__file__).resolve().parent.parent
    assert subprocess.run(cmd, cwd=root, capture_output=True).returncode == 0
    rep = A.recompute()                                                   # chemins réels ; aucune annotation humaine n'existe encore -> rapport vide
    A.to_markdown(rep)
    assert rep["n_items_benchmark"] == 130 and rep["validation_humaine_complete"]["atteinte"] is False
    assert subprocess.run(cmd, cwd=root, capture_output=True).returncode == 0


CAS_HEADER = "cas;juriste;question_juridiquement_valide;source_retrouvee_pertinente;reponse_juridiquement_correcte;version_temporelle_correcte;citation_correcte;hallucination;le_systeme_aurait_du_refuser;qualification;commentaire"
ARB_HEADER = "texte;juriste;reference_correcte;date_de_reference_retenue;commentaire"


def _csv(td, name, header, *rows):
    p = Path(td) / name
    p.write_text("﻿" + "\n".join([header, *rows]) + "\n", encoding="utf-8")
    return p


def test_sheets_for_critical_cases_and_fr_ar_arbitration_are_recorded_validated_and_never_applied():
    with tempfile.TemporaryDirectory() as td:
        ann = Path(td) / "ann"
        overrides = A.ROOT / "boa_pipeline" / "twin_overrides.json"
        before = hashlib.sha256(overrides.read_bytes()).hexdigest()
        ok = _csv(td, "cas.csv", CAS_HEADER, "H120;Me Test;oui;non;non;oui;non;non;oui;reponse_hors_sujet;", "H129;Me Test;oui;oui;non;non;oui;non;non;erreur_juridique_critique;périmée présentée comme actuelle",
                  "H130;;;;;;;;;;")
        s = A.ingest_sheet(ok, ann)
        assert s["kind"] == "cas_critiques" and s["enregistrees"] == 2 and s["lignes_vides_ignorees"] == 1                   # la ligne non remplie n'est jamais complétée
        for bad, msg in ((_csv(td, "b1.csv", CAS_HEADER, "H120;Me Test;peut-être;non;non;oui;non;non;oui;refus_a_tort;"), "hors liste"),
                         (_csv(td, "b2.csv", CAS_HEADER, "H999;Me Test;oui;oui;oui;oui;oui;non;non;non_erreur;"), "inconnu"),
                         (_csv(td, "b3.csv", CAS_HEADER, "H120;Me Test;oui;oui;oui;oui;oui;non;non;autre;"), "commentaire est obligatoire"),
                         (_csv(td, "b4.csv", CAS_HEADER, "H120;;oui;oui;oui;oui;oui;non;non;non_erreur;"), "obligatoire")):
            try:
                A.ingest_sheet(bad, ann)
                raise AssertionError("fiche invalide acceptée : " + msg)
            except ValueError as ex:
                assert msg in str(ex), str(ex)
        try:
            A.ingest_sheet(ok, ann)
            raise AssertionError("double import accepté")
        except ValueError as ex:
            assert "déjà ingéré" in str(ex)
        arb = _csv(td, "arb.csv", ARB_HEADER, "REG-90-01;Me Test;INDETERMINE;;les deux PDF se contredisent", "REG-02-01;;;;", "REG-06-01;Me Test;DEUX_TEXTES_DISTINCTS;;deux règlements différents")
        assert A.ingest_sheet(arb, ann)["enregistrees"] == 2
        bench, _ = _bench(td)
        rep = A.recompute(bench, ann, [])
        assert rep["cas_critiques"]["qualifications_du_juriste"]["H129"]["qualification"] == "erreur_juridique_critique" and "H129" in rep["cas_critiques"]["divergence_notation_automatique_vs_analyse_qualitative"]
        assert rep["arbitrage_jumeaux_fr_ar"]["decisions_du_juriste"]["REG-90-01"]["reference_correcte"] == "INDETERMINE"
        assert hashlib.sha256(overrides.read_bytes()).hexdigest() == before                                              # l'arbitrage n'est jamais appliqué automatiquement au pipeline


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
