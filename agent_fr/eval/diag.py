"""Diagnostic : qualité de la recherche SANS le filtre de refus (rang du passage attendu)."""
import json, sys
from pathlib import Path
from agent_fr.agent import get_index
from agent_fr import retrieve

idx = get_index()
retrieve.MIN_COVERAGE = retrieve.MIN_RATIO = 0.0
rows = [json.loads(l) for l in open(Path(__file__).parent / "gold_v2.jsonl", encoding="utf-8")]
stat = {}
for r in rows:
    if r.get("expect_refuse") or not r.get("expected"):
        continue
    res = retrieve.search(idx, r["question"], k=10)
    exp = r["expected"]
    rank = None
    for n, h in enumerate(res.hits, 1):
        if any(h.chunk["work_id"] == e["work_id"] and (e["article"] is None or h.chunk.get("article") == e["article"]) for e in exp):
            rank = n; break
    best = res.hits[0] if res.hits else None
    stat.setdefault(r["split"], []).append(rank)
    if "-v" in sys.argv:
        print(r["split"], r["id"], "rang", rank, f"cov={best.coverage:.2f} ratio={best.ratio:.2f}" if best else "", "|", r["question"][:60])
for sp, v in stat.items():
    n = len(v)
    print(sp, f"n={n}  rang1={sum(1 for x in v if x==1)}  top3={sum(1 for x in v if x and x<=3)}  top5={sum(1 for x in v if x and x<=5)}  top10={sum(1 for x in v if x)}")
