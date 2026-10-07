"""Exécute le benchmark juridique sur un split (DEV ou TEST) et ENREGISTRE les sorties brutes (récupération, sources données au LLM, réponse, citations, notes, temps).
La notation est faite à part (score.py) à partir de ces sorties : on peut re-noter après une correction humaine du benchmark SANS ré-exécuter le système.

Le split TEST ne doit être exécuté qu'UNE fois, règles de recherche figées ; ses sorties sont alors gelées (SHA-256 dans le manifeste).
Usage : python -m agent_fr.eval.human.run_bench --bench agent_fr/eval/human/benchmark_v1.jsonl --split DEV --pipeline hybrid_rerank --tag dev1 [--no-llm]
        (AGENT_CORPUS_DIR = instantané du corpus évalué)"""
import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "agent_fr" / "eval" / "results"
CACHE = ROOT / "llm_local" / "results" / "llm_cache.jsonl"


def install_llm_cache():
    from agent_fr import llm_backends
    cache = {}
    if CACHE.exists():
        for l in open(CACHE, encoding="utf-8"):
            d = json.loads(l)
            cache[d["key"]] = d["out"]
    real = llm_backends.complete
    stats = {"hits": 0, "calls": 0}

    def cached(system, user, prov=None):
        key = hashlib.sha256(("local|" + system + "|" + user).encode()).hexdigest()
        if key in cache:
            stats["hits"] += 1
            return dict(cache[key], cached=True)
        out = real(system, user, prov)
        stats["calls"] += 1
        cache[key] = out
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "out": out}, ensure_ascii=False) + "\n")
        return out
    llm_backends.complete = cached
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--split", required=True, choices=["DEV", "TEST", "ALL"])
    ap.add_argument("--pipeline", default="hybrid_rerank")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.environ["AGENT_LLM"] = "local"
    if not os.environ.get("AGENT_CORPUS_DIR"):
        print("AGENT_CORPUS_DIR non défini : l'évaluation porte sur le corpus vivant (non figé).", file=sys.stderr)
    from agent_fr import answer
    from agent_fr.agent import get_index
    from agent_fr.pipelines import get_pipeline
    stats = install_llm_cache() if not a.no_llm else {}
    items = [json.loads(l) for l in open(a.bench, encoding="utf-8") if l.strip()]
    items = [i for i in items if a.split == "ALL" or i["split"] == a.split]
    if a.limit:
        items = items[:a.limit]
    idx = get_index()
    search = get_pipeline(a.pipeline)
    recs = []
    for it in items:
        t0 = time.perf_counter()
        res10 = search(idx, it["question"], 10)                         # classement pour les MÉTRIQUES de retrieval (Recall@10) ...
        t_search = (time.perf_counter() - t0) * 1000
        res = search(idx, it["question"], a.k)                          # ... et chemin de PRODUCTION (k = 6) pour le contexte du LLM
        seen, ranked = set(), []
        for h in res10.hits:
            key = (h.chunk["work_id"], h.chunk.get("article"))
            if key in seen:
                continue
            seen.add(key)
            ranked.append({"work_id": h.chunk["work_id"], "article": h.chunk.get("article"), "chunk_id": h.chunk["chunk_id"], "date": h.chunk.get("date"),
                           "langue": h.chunk.get("language"), "score": round(h.score, 4), "via": h.via, "superseded_by": getattr(h, "superseded_by", "")})
        rec = {"id": it["id"], "split": it["split"], "pipeline": a.pipeline, "found": res.found, "clarify": bool(getattr(res, "clarify", False)),
               "reason": res.reason, "retrieval_notes": res.notes, "retrieved": ranked[:10], "search_ms": round(t_search, 1), "timings": getattr(res, "timings", {})}
        if not a.no_llm:
            try:
                out = answer.llm(idx, res, a.k)
            except Exception as e:                                  # une panne isolée est comptée comme échec, pas comme arrêt de l'évaluation
                out = {"mode": "erreur", "found": False, "answer": "", "citations": [], "notes": [f"{type(e).__name__}: {str(e)[:200]}"]}
        else:
            out = answer.extractive(idx, res, min(a.k, 5))
        srcs = out.get("sources") or out.get("citations") or []
        rec.update({"mode": out.get("mode"), "answer_found": out.get("found"), "answer_clarify": bool(out.get("clarify")), "answer": out.get("answer", ""),
                    "citations": [c["chunk_id"] for c in out.get("citations", [])],
                    "sources": [{"id": c["id"], "chunk_id": c["chunk_id"], "work_id": c["chunk_id"].split("::")[0].rsplit(".", 1)[0], "article": c.get("article"),
                                 "texte": c["extrait"], "meta": f"{c.get('texte')} | {c.get('date')} | {c.get('titre')} | article {c.get('article')} | statut_juridique={c.get('statut_juridique')} | relations={json.dumps(c.get('relations_prompt') or {}, ensure_ascii=False)}", "statut_juridique": c.get("statut_juridique"), "statut_detail": c.get("statut_detail"),
                                 "document_url": c.get("document_url"), "source_url": c.get("source_url"), "page": c.get("page")} for c in srcs],
                    "notes": out.get("notes", []), "latency_llm_s": out.get("latency_s"),
                    "total_s": round(t_search / 1000 + (out.get("latency_s") or 0), 2)})
        recs.append(rec)
        print(it["id"], it["type_de_question"], rec["mode"], f"{rec['total_s']}s", flush=True)
    dst = RESULTS / f"human_bench_{a.tag}.json"
    meta = {"tag": a.tag, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "pipeline": a.pipeline, "split": a.split, "bench": str(a.bench),
            "bench_sha256": hashlib.sha256(Path(a.bench).read_bytes()).hexdigest(), "corpus": os.environ.get("AGENT_CORPUS_DIR"), "llm": not a.no_llm,
            "llm_cache": stats, "n": len(recs), "records": recs}
    dst.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("écrit :", dst, "| sha256", hashlib.sha256(dst.read_bytes()).hexdigest()[:16])


if __name__ == "__main__":
    main()
