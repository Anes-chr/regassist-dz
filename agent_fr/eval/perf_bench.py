"""Mesure CPU / RAM / disque / latence du moteur de recherche (à lancer machine au repos : pas d'évaluation LLM en parallèle).

Mesures : RSS du processus de l'agent à chaque étape (imports → index → embedder + vecteurs + reranker), latence de 40 questions réelles
(embedding, recherche, reranking, total ; moyenne / médiane / p95), RAM utilisée par llama-server s'il tourne, taille disque des modèles et index.
Usage : python -m agent_fr.eval.perf_bench [--n 40] [--tag perf_phase2]"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

import psutil

os.environ.setdefault("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06")
HERE = Path(__file__).resolve().parent
ME = psutil.Process()


def mb(x):
    return round(x / 1e6, 1)


def rss():
    return mb(ME.memory_info().rss)


def du(path):
    p = Path(path)
    if not p.exists():
        return None
    if p.is_file():
        return mb(p.stat().st_size)
    return mb(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()))


def stats(xs):
    xs = sorted(xs)
    return {"moy": round(statistics.mean(xs), 1), "mediane": round(statistics.median(xs), 1), "p95": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 1), "max": round(xs[-1], 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--tag", default="perf_phase2")
    a = ap.parse_args()
    out = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "machine": {"cpu_logiques": psutil.cpu_count(), "ram_totale_mb": mb(psutil.virtual_memory().total)}}
    out["ram_libre_avant_mb"] = mb(psutil.virtual_memory().available)
    out["rss_mb"] = {"processus_vide": rss()}
    from agent_fr.agent import get_index
    from agent_fr.pipelines import get_pipeline
    idx = get_index()
    out["rss_mb"]["apres_index_corpus"] = rss()
    rows = []
    for l in open(HERE / "gold_v5.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if not r.get("expect_clarify") and not r.get("expect_refuse"):
            rows.append(r["question"])
    for l in open(HERE / "gold_v4.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if not r.get("expect_clarify") and not r.get("expect_refuse") and len(rows) < a.n:
            rows.append(r["question"])
    rows = rows[:a.n]
    out["n_questions"] = len(rows)
    out["pipelines"] = {}
    for name in ("legacy", "hybrid", "hybrid_rerank"):
        search = get_pipeline(name)
        if name != "legacy":
            t0 = time.perf_counter()
            search(idx, rows[0], 10)
            out["rss_mb"][f"apres_chargement_{name}"] = rss()
            out.setdefault("premier_appel_s", {})[name] = round(time.perf_counter() - t0, 2)
        search(idx, rows[1], 10)   # chauffe
        tot, emb, srch, rr = [], [], [], []
        peak = rss()
        cpu0 = ME.cpu_times()
        wall0 = time.perf_counter()
        for q in rows:
            t0 = time.perf_counter()
            res = search(idx, q, 10)
            tot.append((time.perf_counter() - t0) * 1000)
            tm = getattr(res, "timings", {}) or {}
            if tm.get("embed_question_ms") is not None:
                emb.append(tm["embed_question_ms"])
            if tm.get("search_ms") is not None:
                srch.append(tm["search_ms"])
            if tm.get("rerank_ms") is not None:
                rr.append(tm["rerank_ms"])
            peak = max(peak, rss())
        wall = time.perf_counter() - wall0
        cpu1 = ME.cpu_times()
        out["pipelines"][name] = {"total_ms": stats(tot), "embedding_ms": stats(emb) if emb else None, "recherche_ms": stats(srch) if srch else None,
                                  "reranking_ms": stats(rr) if rr else None, "rss_pic_mb": peak,
                                  "cpu_utilise_coeurs_moy": round(((cpu1.user + cpu1.system) - (cpu0.user + cpu0.system)) / wall, 2)}
    out["rss_mb"]["final"] = rss()
    llama = [p for p in psutil.process_iter(["name", "memory_info"]) if (p.info["name"] or "").lower().startswith("llama-server")]
    out["llama_server_rss_mb"] = mb(llama[0].info["memory_info"].rss) if llama else "serveur arrêté (non mesuré)"
    out["ram_libre_apres_mb"] = mb(psutil.virtual_memory().available)
    out["disque_mb"] = {"modele_embeddings_e5_small": du("D:/llm/models/embeddings"), "modele_reranker_mmarco_int8": du("D:/llm/models/rerankers"),
                        "index_vecteurs": du("D:/llm/index"), "instantane_corpus_figé": du("D:/llm/snapshots/corpus_2026-10-06"),
                        "modele_llm_qwen3_4b_q4km": du("D:/llm/models/llm") or du("D:/llm/models"), "llama_cpp": du("D:/llm/llama.cpp") or du("D:/llm/bin")}
    dst = HERE / "results" / f"{a.tag}.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("écrit :", dst)


if __name__ == "__main__":
    main()
