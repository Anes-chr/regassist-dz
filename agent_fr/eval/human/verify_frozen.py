"""Vérifie que TEST v1 (phase 3) est strictement inchangé : questions, réponses attendues, règles de notation, critères de décision, sorties brutes et notées.
`python -m agent_fr.eval.human.verify_frozen --init` écrit l'empreinte de référence (une seule fois, à l'ouverture de la phase 4) ; sans option, compare et sort en code 1 si une empreinte diffère.
Le moteur lui-même n'est PAS figé en phase 4 (le corpus et la chaîne de construction changent) : seul TEST v1 l'est, ainsi que son manifeste de règles de la phase 3."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REF = Path(__file__).resolve().parent / "frozen_test_v1.sha256.json"
FILES = [
    "agent_fr/eval/results/human_bench_test_final.json",       # sorties brutes de TEST v1
    "agent_fr/eval/results/human_score_test_final.json",       # sorties notées de TEST v1
    "agent_fr/eval/results/human_bench_dev_final2.json",       # DEV de la phase 3 (référence de comparaison)
    "agent_fr/eval/results/human_score_dev_final2.json",
    "agent_fr/eval/results/FROZEN_SHA256.txt",
    "agent_fr/eval/human/benchmark_v1_draft.jsonl",            # questions + réponses attendues (DEV et TEST v1)
    "agent_fr/eval/human/bench.py",                            # règles de notation (en-tête)
    "agent_fr/eval/human/score.py",
    "agent_fr/eval/human/run_bench.py",
    "agent_fr/eval/human/decision_criteria.md",
    "agent_fr/eval/human/frozen_rules_manifest.json",
]


def sha(p):
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def main():
    if "--init" in sys.argv:
        if REF.exists():
            sys.exit("référence déjà écrite : elle ne se réécrit jamais")
        REF.write_text(json.dumps({f: sha(f) for f in FILES}, indent=1), encoding="utf-8")
        print("référence écrite :", REF)
        return
    ref = json.loads(REF.read_text(encoding="utf-8"))
    bad = [f for f, h in ref.items() if not (ROOT / f).exists() or sha(f) != h]
    print(f"{len(ref)} fichiers de TEST v1 vérifiés ; modifiés : {bad if bad else 'aucun'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
