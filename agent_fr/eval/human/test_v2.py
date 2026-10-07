"""TEST v2 — protocole d'un test INDÉPENDANT, impossible à utiliser pour régler le système puis à présenter comme une mesure indépendante.

TEST v1 est consommé et gelé (verify_frozen.py). TEST v2 n'existe pas encore : il ne sera créé qu'APRÈS (1) correction du corpus, (2) décision OCR documentée, (3) validation humaine du benchmark et des
réponses, (4) gel des règles. Garde-fous :
  * les questions sont RÉDIGÉES PAR UN HUMAIN (juriste) : `author-template` fournit le gabarit, `validate` refuse un fichier dont l'auteur n'est pas humain, qui reprend une question de DEV / TEST v1,
    ou dont un passage cité n'existe pas mot pour mot dans le corpus ; AUCUNE question n'est rédigée par l'assistant IA ;
  * `freeze` écrit un manifeste (empreintes des questions, du code qui influence les résultats, du corpus, des vecteurs, des modèles, des critères de décision) et refuse si un prérequis manque ;
  * `run` refuse si le manifeste est absent, si une empreinte de code a changé depuis le gel, ou si TEST v2 a déjà été exécuté (verrou LOCK écrit AVANT l'exécution, jamais supprimé) ;
  * les sorties sont mises en lecture seule avec leur empreinte ; une correction ultérieure se fait par RE-NOTATION, jamais par ré-exécution.
Usage : python -m agent_fr.eval.human.test_v2 status | author-template | validate --file F | freeze --file F --corpus DIR --confirm-no-tuning | run
"""
import argparse
import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
V2 = HERE / "test_v2"
QUESTIONS = V2 / "test_v2_questions.jsonl"
MANIFEST = V2 / "MANIFEST.json"
LOCK = V2 / "LOCK"
RESULTS = ROOT / "agent_fr" / "eval" / "results"
MIN_ITEMS = 100
FORBIDDEN_AUTHORS = ("claude", "gpt", "llm", "ia ", " ia", "assistant", "ai ", "qwen", "anthropic", "openai", "automatique")
CODE_GLOBS = ["agent_fr/*.py", "boa_pipeline/*.py", "agent_fr/eval/human/bench.py", "agent_fr/eval/human/score.py", "agent_fr/eval/human/run_bench.py", "agent_fr/eval/human/test_v2.py",
              "agent_fr/eval/human/decision_criteria.md", "boa_pipeline/twin_overrides.json"]
MODEL_FILES = [Path("D:/llm/models/qwen3-4b-instruct-2507-q4_k_m.gguf")]


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def code_hashes(root=ROOT, globs=None) -> dict:
    out = {}
    for g in globs or CODE_GLOBS:
        for p in sorted(Path(root).glob(g)):
            out[str(p.relative_to(root)).replace("\\", "/")] = sha(p)
    return out


def model_hashes() -> dict:
    out = {}
    base = Path(os.environ.get("AGENT_MODELS", "D:/llm/models"))
    for p in sorted(base.rglob("*.onnx")) + sorted(base.rglob("tokenizer.json")) + [m for m in MODEL_FILES if m.exists()]:
        out[str(p).replace("\\", "/")] = {"bytes": p.stat().st_size, "sha256": sha(p)}
    return out


def v1_questions() -> set:
    bench = HERE / "benchmark_v1_draft.jsonl"
    norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
    return {norm(json.loads(l)["question"]) for l in bench.read_text(encoding="utf-8").splitlines() if l.strip()}


# --------------------------------------------------------------------------- prérequis
def prerequisites(corpus_report=None, ocr_scores=None) -> dict:
    """Les 4 conditions de création de TEST v2, vérifiées sur des fichiers (jamais déclarées)."""
    res = {}
    cr = Path(corpus_report or RESULTS / "corpus_check_phase4.json")
    if cr.exists():
        rep = json.loads(cr.read_text(encoding="utf-8"))
        bloc = [a for a in rep["anomalies"] if a["niveau"] == "BLOQUANT"]
        res["1_corpus_corrige"] = {"ok": not bloc, "detail": f"{len(bloc)} anomalie(s) BLOQUANT dans {cr.name}"}
    else:
        res["1_corpus_corrige"] = {"ok": False, "detail": "rapport de contrôle du corpus absent"}
    oc = Path(ocr_scores or RESULTS / "ocr_bench_scores.json")
    doc = ROOT / "docs" / "RETRIEVAL_PHASE4.md"
    res["2_ocr_decide"] = {"ok": oc.exists() and doc.exists(), "detail": "benchmark OCR mesuré et décision documentée (docs/RETRIEVAL_PHASE4.md)" if oc.exists() and doc.exists() else "benchmark OCR ou décision documentée absents"}
    try:
        from agent_fr.eval.human import annotations
        v = annotations.recompute()["validation_humaine_complete"]
        res["3_validation_humaine"] = {"ok": v["atteinte"], "detail": f"{v['definition']} ; benchmark couvert {v['benchmark_couvert']}, réponses évaluées {v['reponses_evaluees']}"}
    except Exception as e:                                                              # noqa: BLE001
        res["3_validation_humaine"] = {"ok": False, "detail": f"{type(e).__name__}: {e}"}
    res["4_regles_gelees"] = {"ok": MANIFEST.exists(), "detail": "manifeste de gel présent" if MANIFEST.exists() else "pas encore gelé (se fait avec `freeze`, après les trois autres)"}
    res["_toutes_reunies_avant_gel"] = all(res[k]["ok"] for k in ("1_corpus_corrige", "2_ocr_decide", "3_validation_humaine"))
    return res


# --------------------------------------------------------------------------- validation du fichier de questions
def validate(path, corpus_dir=None) -> dict:
    items = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    errors = []
    v1 = v1_questions()
    norm = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
    seen = set()
    for it in items:
        iid = it.get("id", "?")
        red = it.get("redaction") or {}
        auteur = f" {str(red.get('auteur', '')).lower()} "
        if red.get("type") != "humain" or not str(red.get("auteur", "")).strip() or any(w in auteur for w in FORBIDDEN_AUTHORS):
            errors.append(f"{iid}: auteur non humain ou absent (redaction.type doit valoir « humain », redaction.auteur = nom du juriste)")
        q = norm(it.get("question", ""))
        if q in v1:
            errors.append(f"{iid}: reprend une question de DEV / TEST v1")
        if q in seen:
            errors.append(f"{iid}: question en double")
        seen.add(q)
    if len(items) < MIN_ITEMS:
        errors.append(f"{len(items)} questions < {MIN_ITEMS} exigées")
    if corpus_dir:
        from agent_fr.eval.human.bench import Corpus, verify_item
        corpus = Corpus(corpus_dir)
        for it in items:
            errors += [f"{it.get('id', '?')}: {e}" for e in verify_item(dict(it, split="TEST") if it.get("split") in ("TEST2", "TEST_V2") else it, corpus)]
    types = {}
    for it in items:
        types[it.get("type_de_question")] = types.get(it.get("type_de_question"), 0) + 1
    return {"n": len(items), "par_type": types, "erreurs": errors, "ok": not errors}


def author_template(out=None):
    out = Path(out or ROOT / "agent_fr" / "eval" / "human" / "review" / "test_v2_authoring.csv")
    out.parent.mkdir(exist_ok=True)
    cols = ["id", "type_de_question", "langue", "domaine", "question", "document_attendu (work_id ou URL du PDF officiel)", "article_attendu", "passage_attendu (copié MOT POUR MOT du PDF officiel)",
            "reponse_attendue", "date_de_reference (actuel / AAAA-MM-JJ / vide)", "statut_juridique (ACTIVE/MODIFIED/REPLACED/ABROGATED/HISTORICAL/UNKNOWN)", "niveau_de_difficulte (facile/moyen/difficile)",
            "attendu_comportement (repondre/refuser/clarifier)", "auteur (votre nom)"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerow(cols)
    note = out.with_suffix(".txt")
    note.write_text("Gabarit de rédaction de TEST v2 (à remplir par un juriste, jamais par l'assistant IA).\n"
                    "Types à couvrir : A direct, B multi-textes, C temporelle, D modification, E abrogation, F comparaison ancien/actuel, G ambiguë, H hors corpus, I hors sujet, J français/arabe.\n"
                    f"Au moins {MIN_ITEMS} questions ; aucune question de DEV ni de TEST v1 ; passages cités mot pour mot ; une fois le fichier validé et gelé, il n'est plus jamais modifié.\n"
                    "Ne regardez pas les réponses du système avant d'écrire : TEST v2 doit rester indépendant.\n", encoding="utf-8")
    return out


# --------------------------------------------------------------------------- gel et exécution
def freeze(path, corpus_dir, confirm: bool, prereq=None) -> dict:
    if not confirm:
        raise SystemExit("REFUSÉ : --confirm-no-tuning est obligatoire (vous attestez qu'aucune règle n'a été réglée avec ces questions).")
    pre = prereq or prerequisites()
    if not pre["_toutes_reunies_avant_gel"]:
        raise SystemExit("REFUSÉ : prérequis non réunis avant le gel : " + json.dumps({k: v for k, v in pre.items() if k != "_toutes_reunies_avant_gel" and not v["ok"] and k != "4_regles_gelees"}, ensure_ascii=False))
    v = validate(path, corpus_dir)
    if not v["ok"]:
        raise SystemExit("REFUSÉ : le fichier de questions n'est pas valide : " + "; ".join(v["erreurs"][:5]))
    if MANIFEST.exists() or LOCK.exists():
        raise SystemExit("REFUSÉ : TEST v2 est déjà gelé ou exécuté.")
    V2.mkdir(exist_ok=True)
    QUESTIONS.write_bytes(Path(path).read_bytes())
    corpus_dir = Path(corpus_dir)
    man = {"gele_le": time.strftime("%Y-%m-%dT%H:%M:%S"), "questions_sha256": sha(QUESTIONS), "n_questions": v["n"], "par_type": v["par_type"],
           "criteres_de_decision_sha256": sha(HERE / "decision_criteria.md"), "code": code_hashes(),
           "corpus": {"dir": str(corpus_dir), "fichiers": {p.name: sha(p) for p in sorted(corpus_dir.glob("*")) if p.is_file()}},
           "vecteurs": {str(p).replace("\\", "/"): sha(p) for p in sorted(Path("D:/llm/index").glob("vec_*.npy"))[-1:]},
           "modeles": model_hashes(), "environnement": {k: os.environ.get(k) for k in ("AGENT_RETRIEVER", "AGENT_LLM", "AGENT_CORPUS_DIR")}, "python": sys.version.split()[0],
           "prerequis": {k: v2 for k, v2 in pre.items() if k != "_toutes_reunies_avant_gel"}}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def check_before_run() -> dict:
    if not MANIFEST.exists():
        raise SystemExit("REFUSÉ : TEST v2 n'est pas gelé (pas de manifeste).")
    if LOCK.exists():
        raise SystemExit("REFUSÉ : TEST v2 a déjà été exécuté (verrou) ; ses sorties sont gelées. Re-notez-les, ne ré-exécutez pas.")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    changed = [f for f, h in man["code"].items() if not (ROOT / f).exists() or sha(ROOT / f) != h]
    if changed:
        raise SystemExit("REFUSÉ : le code a changé depuis le gel : " + ", ".join(changed[:8]))
    if sha(QUESTIONS) != man["questions_sha256"]:
        raise SystemExit("REFUSÉ : les questions ont changé depuis le gel.")
    cdir = Path(man["corpus"]["dir"])
    if any(not (cdir / n).exists() or sha(cdir / n) != h for n, h in man["corpus"]["fichiers"].items()):
        raise SystemExit("REFUSÉ : le corpus a changé depuis le gel.")
    return man


def run():
    man = check_before_run()
    LOCK.write_text(json.dumps({"debut": time.strftime("%Y-%m-%dT%H:%M:%S"), "questions_sha256": man["questions_sha256"]}), encoding="utf-8")   # verrou écrit AVANT l'exécution, jamais supprimé
    env = dict(os.environ, AGENT_CORPUS_DIR=man["corpus"]["dir"], AGENT_LLM="local")
    r = subprocess.run([sys.executable, "-m", "agent_fr.eval.human.run_bench", "--bench", str(QUESTIONS), "--split", "ALL", "--pipeline", "hybrid_rerank", "--tag", "test_v2"], cwd=str(ROOT), env=env)
    out = RESULTS / "human_bench_test_v2.json"
    if out.exists():
        os.chmod(out, stat.S_IREAD)
        (RESULTS / "FROZEN_SHA256_TEST_V2.txt").write_text(f"{sha(out)}  {out.name}\n", encoding="utf-8")
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    sp.add_parser("author-template")
    s = sp.add_parser("validate")
    s.add_argument("--file", required=True)
    s.add_argument("--corpus", default=None)
    s = sp.add_parser("freeze")
    s.add_argument("--file", required=True)
    s.add_argument("--corpus", required=True)
    s.add_argument("--confirm-no-tuning", action="store_true")
    sp.add_parser("run")
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "status":
        print(json.dumps({"prerequis": prerequisites(), "questions_presentes": QUESTIONS.exists(), "gele": MANIFEST.exists(), "execute": LOCK.exists()}, ensure_ascii=False, indent=1))
    elif a.cmd == "author-template":
        print("écrit :", author_template())
    elif a.cmd == "validate":
        print(json.dumps(validate(a.file, a.corpus), ensure_ascii=False, indent=1))
    elif a.cmd == "freeze":
        print(json.dumps(freeze(a.file, a.corpus, a.confirm_no_tuning), ensure_ascii=False, indent=1)[:1500])
    else:
        sys.exit(run())


if __name__ == "__main__":
    main()
