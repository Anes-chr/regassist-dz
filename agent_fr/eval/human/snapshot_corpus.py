"""Fige le corpus vivant dans un instantané plat horodaté (évaluations reproductibles) : chunks, documents, statut juridique, empreintes SHA-256, puis vecteurs (cache incrémental).
Rien n'est supprimé ni modifié dans corpus/ : on COPIE. Usage : python -m agent_fr.eval.human.snapshot_corpus [--name corpus_final_2026-10-07]"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = [("corpus/chunks/chunks_fr.jsonl", "chunks_fr.jsonl"), ("corpus/chunks/chunks_ar.jsonl", "chunks_ar.jsonl"), ("corpus/chunks/chunks_und.jsonl", "chunks_und.jsonl"),
         ("corpus/metadata/documents_fr.json", "documents_fr.json"), ("corpus/metadata/documents_ar.json", "documents_ar.json"), ("corpus/metadata/documents_und.json", "documents_und.json"),
         ("corpus/metadata/legal_status.json", "legal_status.json")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="corpus_final_" + time.strftime("%Y-%m-%d"))
    a = ap.parse_args()
    dst = Path("D:/llm/snapshots") / a.name
    if dst.exists():
        sys.exit(f"{dst} existe déjà : choisissez un autre nom (un instantané n'est jamais écrasé)")
    dst.mkdir(parents=True)
    sums = []
    for src, name in FILES:
        p = ROOT / src
        if not p.exists():
            print("absent (ignoré) :", src)
            continue
        shutil.copy2(p, dst / name)
        sums.append(f"{hashlib.sha256((dst / name).read_bytes()).hexdigest()}  {name}")
    (dst / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    env = dict(os.environ, AGENT_CORPUS_DIR=str(dst))
    r = subprocess.run([sys.executable, "-m", "agent_fr.build_vectors"], cwd=str(ROOT), env=env)
    print("vecteurs :", "ok" if r.returncode == 0 else f"échec (code {r.returncode})")
    print("instantané :", dst)
    print("\n".join(sums))


if __name__ == "__main__":
    main()
