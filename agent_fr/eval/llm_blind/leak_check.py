"""Contrôle anti-fuite : refuse tout jeu d'entraînement qui contient une question du jeu aveugle ou l'un de ses passages sources.
Usage : python agent_fr/eval/llm_blind/leak_check.py chemin/vers/train.jsonl
Le fichier est parcouru ligne à ligne ; tout le texte de chaque ligne (JSON aplati) est comparé. Code de sortie 1 en cas de fuite."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(s):
    return " ".join(str(s).replace("’", "'").lower().split())


def flatten(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from flatten(v)
    elif isinstance(o, list):
        for v in o:
            yield from flatten(v)
    else:
        yield str(o)


def main(path):
    man = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    qs, cids = man["exclude_questions_normalized"], set(man["exclude_chunk_ids"])
    leaks = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            blob = norm(" ".join(flatten(json.loads(line))))
        except json.JSONDecodeError:
            blob = norm(line)
        for q in qs:
            if q and q in blob:
                leaks.append((n, "question du jeu aveugle", q[:70]))
        for c in cids:
            if c.lower() in blob:
                leaks.append((n, "passage du jeu aveugle", c))
    if leaks:
        print(f"FUITE : {len(leaks)} chevauchement(s) avec le jeu aveugle")
        for l in leaks[:20]:
            print("  ligne", *l)
        sys.exit(1)
    print("OK : aucun chevauchement avec le jeu aveugle")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
