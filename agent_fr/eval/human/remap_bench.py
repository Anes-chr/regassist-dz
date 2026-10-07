"""Copie DÉRIVÉE du benchmark pour un corpus dont certains identifiants de textes (work_id) ont changé (phase 4 : jumeaux FR/AR rattachés, suffixes de date retirés).
Le fichier source (benchmark_v1_draft.jsonl : questions, réponses attendues, TEST v1) n'est JAMAIS modifié : seule une copie est écrite, avec la table de correspondance et les empreintes.
La correspondance ancien -> nouveau work_id se fait par l'empreinte du fichier source (file_hash), jamais par heuristique ; un identifiant ambigu arrête le script.
Usage : python -m agent_fr.eval.human.remap_bench --old D:/llm/snapshots/corpus_phase3_final --new D:/llm/snapshots/corpus_phase4 --split DEV --out agent_fr/eval/human/benchmark_dev_phase4.jsonl"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parent / "benchmark_v1_draft.jsonl"


def docs(base):
    out = []
    for lg in ("fr", "ar", "und"):
        p = Path(base) / f"documents_{lg}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            out += d if isinstance(d, list) else list(d.values())
    return out


def mapping(old_dir, new_dir):
    by_hash = collections.defaultdict(set)
    for d in docs(new_dir):
        by_hash[d["file_hash"]].add(d["work_id"])
    m, ambiguous, missing = {}, {}, []
    for d in docs(old_dir):
        news = by_hash.get(d["file_hash"], set())
        if len(news) == 1:
            m.setdefault(d["work_id"], set()).add(next(iter(news)))
        elif news:
            ambiguous[d["work_id"]] = sorted(news)
        else:
            missing.append(d["work_id"])
    amb2 = {w: sorted(v) for w, v in m.items() if len(v) > 1}
    return {w: next(iter(v)) for w, v in m.items() if len(v) == 1}, {**ambiguous, **amb2}, missing


def walk(x, table, hits):
    if isinstance(x, dict):
        return {k: walk(v, table, hits) for k, v in x.items()}
    if isinstance(x, list):
        return [walk(v, table, hits) for v in x]
    if isinstance(x, str) and x in table:
        hits[x] += 1
        return table[x]
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--split", choices=["DEV", "TEST", "ALL"], default="DEV")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m, amb, missing = mapping(a.old, a.new)
    changed = {w: n for w, n in m.items() if w != n}
    items = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    used = {e["work_id"] for it in items for k in ("document_attendu", "article_attendu", "passage_attendu", "versions_interdites") for e in (it.get(k) or []) if e.get("work_id")}
    used |= {it["sujet"]["work_id"] for it in items if isinstance(it.get("sujet"), dict) and it["sujet"].get("work_id")}
    bad = sorted(w for w in used if w in amb or w in missing)
    if bad:
        sys.exit(f"identifiants utilisés par le benchmark mais ambigus ou absents du nouveau corpus : {bad}")
    hits = collections.Counter()
    out = []
    for it in items:
        if a.split != "ALL" and it["split"] != a.split:
            continue
        out.append(walk(it, changed, hits))
    dst = Path(a.out)
    dst.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n", encoding="utf-8")
    rep = {"source": str(SRC), "source_sha256": hashlib.sha256(SRC.read_bytes()).hexdigest(), "derivee": str(dst), "derivee_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
           "split": a.split, "items": len(out), "ancien_corpus": a.old, "nouveau_corpus": a.new, "identifiants_changes": changed, "remplacements_effectues": dict(hits),
           "identifiants_utilises_par_le_benchmark_et_changes": sorted(w for w in used if w in changed)}
    dst.with_suffix(".remap.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("items", "identifiants_changes", "remplacements_effectues", "identifiants_utilises_par_le_benchmark_et_changes")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
