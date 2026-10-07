"""Encode les chunks du corpus (FR puis AR) avec multilingual-e5-small et écrit D:\\llm\\index\\vec_<clé>.npy + .meta.json.
Usage : python -m agent_fr.build_vectors [--threads 6] [--langs fr,ar]   (corpus : AGENT_CORPUS_DIR, sinon corpus/chunks)"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from .embed import INDEX_DIR, Embedder, corpus_key, passage_text, vector_path

ROOT = Path(__file__).resolve().parent.parent


def chunk_files(langs):
    snap = os.environ.get("AGENT_CORPUS_DIR")
    base = Path(snap) if snap else ROOT / "corpus" / "chunks"
    return [(lg, base / f"chunks_{lg}.jsonl") for lg in langs if (base / f"chunks_{lg}.jsonl").exists()]


def load_chunks(langs):
    rows = []
    for lg, p in chunk_files(langs):
        for l in open(p, encoding="utf-8"):
            rows.append(json.loads(l))
    return rows


def vectors_key(langs):
    parts = [str(corpus_key(p, lg)) for lg, p in chunk_files(langs)]
    import hashlib
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--langs", default="fr,ar")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    langs = a.langs.split(",")
    key = vectors_key(langs)
    dst = vector_path(key)
    chunks = load_chunks(langs)
    cache_f = INDEX_DIR / "vec_cache_e5small.npz"
    if dst.exists() and not a.force:
        if not cache_f.exists():            # amorce le cache incrémental à partir des vecteurs existants (aucun ré-encodage)
            vecs0 = np.load(dst)
            if len(vecs0) == len(chunks):
                uniq = {}
                for c, v in zip(chunks, vecs0):
                    uniq.setdefault(hashlib.sha1(passage_text(c).encode("utf-8")).hexdigest(), v)
                np.savez(cache_f, hashes=np.array(list(uniq)), vecs=np.stack(list(uniq.values())))
                print(f"cache incrémental amorcé : {len(uniq)} textes distincts")
        print("vecteurs déjà présents :", dst)
        return
    texts = [passage_text(c) for c in chunks]
    hashes = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
    # cache incrémental : un chunk dont le texte n'a pas changé n'est pas ré-encodé
    cache = {}
    if cache_f.exists() and not a.force:
        z = np.load(cache_f, allow_pickle=False)
        cache = dict(zip(z["hashes"].tolist(), z["vecs"]))
    todo = [i for i, h in enumerate(hashes) if h not in cache]
    print(f"{len(chunks)} chunks ({a.langs}) : {len(chunks) - len(todo)} réutilisés du cache, {len(todo)} à encoder — threads={a.threads}", flush=True)
    t0 = time.time()
    if todo:
        emb = Embedder(a.threads)
        newv = emb.embed([texts[i] for i in todo], prefix="passage: ", batch=16, progress=True)
        for i, v in zip(todo, newv):
            cache[hashes[i]] = v
    vecs = np.stack([cache[h] for h in hashes]).astype(np.float32)
    keep = set(hashes)
    np.savez(cache_f, hashes=np.array([h for h in cache if h in keep]), vecs=np.stack([cache[h] for h in cache if h in keep]))
    dt = time.time() - t0
    np.save(dst, vecs)
    meta = {"key": key, "langs": langs, "n": len(chunks), "dim": int(vecs.shape[1]), "model": "intfloat/multilingual-e5-small (onnx fp32)",
            "seconds": round(dt, 1), "encoded": len(todo), "reused": len(chunks) - len(todo), "chunks_per_s": round(max(len(todo), 1) / max(dt, 1e-6), 2), "chunk_ids": [c["chunk_id"] for c in chunks],
            "language": [c.get("language") for c in chunks], "size_mb": round(vecs.nbytes / 1e6, 1)}
    dst.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"terminé en {dt / 60:.1f} min ({len(todo)} encodés, {len(chunks) - len(todo)} réutilisés) -> {dst} ({meta['size_mb']} Mo)")


if __name__ == "__main__":
    main()
