"""Évaluation de BOUT EN BOUT : question → recherche → contexte → Qwen3-4B local → réponse + citations.

Pour chaque question on enregistre : passages récupérés (+ scores), sources données au LLM, réponse, citations, verdict, temps (recherche / reranking /
LLM / total). Les réponses du LLM sont mises en cache (clé = empreinte de la consigne + du contexte) : deux pipelines qui fournissent le même
contexte ne recalculent pas ; la latence d'origine est conservée pour le calcul des temps.
Notation automatique : faits clés présents (espaces et séparateurs normalisés), source attendue citée, refus / clarification corrects.
Usage : python -m agent_fr.eval.e2e_eval --pipeline hybrid_rerank --sets v3,v4 --tag e2e_hybrid_rerank   (serveur llama local démarré)"""
import argparse
import hashlib
import json
import os
import re
import statistics
import time
from pathlib import Path

os.environ.setdefault("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06")
os.environ["AGENT_LLM"] = "local"
from agent_fr import answer, llm_backends  # noqa: E402
from agent_fr.agent import get_index  # noqa: E402
from agent_fr.pipelines import get_pipeline  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = ROOT / "llm_local" / "results" / "llm_cache.jsonl"
_cache = {}
if CACHE.exists():
    for l in open(CACHE, encoding="utf-8"):
        d = json.loads(l)
        _cache[d["key"]] = d["out"]
_real_complete = llm_backends.complete
_stats = {"hits": 0, "calls": 0}


def cached_complete(system, user, prov=None):
    key = hashlib.sha256(("local|" + system + "|" + user).encode()).hexdigest()
    if key in _cache:
        _stats["hits"] += 1
        return dict(_cache[key], cached=True)
    out = _real_complete(system, user, prov)
    _stats["calls"] += 1
    _cache[key] = out
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "out": out}, ensure_ascii=False) + "\n")
    return out


llm_backends.complete = cached_complete


def squash(s):
    s = str(s).replace("’", "'").lower().replace("\u00a0", " ")
    return re.sub(r"\s+", "", s)


def has_fact(text, fact):
    return squash(fact) in squash(text)


def load(sets):
    rows = []
    for st in sets:
        for l in open(HERE / f"gold_{st}.jsonl", encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                r["set"] = st
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="hybrid_rerank")
    ap.add_argument("--sets", default="v3,v4")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--k", type=int, default=6)
    a = ap.parse_args()
    idx = get_index()
    search = get_pipeline(a.pipeline)
    rows = load(a.sets.split(","))
    recs = []
    for r in rows:
        t0 = time.perf_counter()
        res = search(idx, r["question"], a.k)
        search_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        try:
            out = answer.llm(idx, res, a.k)
        except Exception as e:                      # une panne isolée ne doit pas faire perdre l'évaluation entière ; elle est comptée comme échec
            out = {"mode": "erreur", "found": False, "answer": "", "citations": [], "notes": [f"{type(e).__name__}: {str(e)[:200]}"]}
        total_s = (time.perf_counter() - t0)
        used_llm = out.get("mode") == "llm"
        ok = {}
        facts = r.get("key_facts") or ([r["key_fact"]] if r.get("key_fact") else [])
        if r.get("expect_refuse"):
            ok["refus"] = not out["found"]
        elif r.get("expect_clarify"):
            ok["clarification"] = bool(out.get("clarify"))
        else:
            exp = r["expected"]
            cited = [c for c in out["citations"] if any(c["chunk_id"].split("::")[0].rsplit(".", 1)[0] == e["work_id"] and (e["article"] is None or str(c["article"]) == e["article"]) for e in exp)]
            ok["source_citee"] = bool(cited)
            if facts:
                ok["faits_cles"] = out["found"] and all(has_fact(out["answer"], f) for f in facts)
            if r.get("stale_top1"):
                stale_cited = [c for c in out["citations"] if c["chunk_id"].split("::")[0].rsplit(".", 1)[0] in r["stale_top1"]]
                ok["sans_valeur_perimee_citee_seule"] = not (stale_cited and not cited)
        recs.append({
            "id": r["id"], "set": r["set"], "category": r["category"], "question": r["question"], "pipeline": a.pipeline,
            "found": out["found"], "clarify": bool(out.get("clarify")), "mode": out.get("mode"), "llm_utilise": used_llm,
            "retrieved": [{"chunk_id": h.chunk["chunk_id"], "work_id": h.chunk["work_id"], "article": h.chunk.get("article"), "date": h.chunk.get("date"),
                           "score": round(h.score, 4), "via": h.via} for h in res.hits[:8]],
            "sources_donnees_au_llm": list(out.get("all_retrieved_chunks") or [c["chunk_id"] for c in out["citations"]]),
            "reponse": out["answer"], "citations": [c["chunk_id"] for c in out["citations"]], "notes": out.get("notes", []),
            "ok": ok, "correct": all(ok.values()),
            "temps": {"recherche_ms": round(search_ms, 1), "embedding_ms": res.timings.get("embed_question_ms"), "rerank_ms": res.timings.get("rerank_ms"),
                      "llm_s": out.get("latency_s") if used_llm else 0.0,
                      "total_s": round(search_ms / 1000 + (out.get("latency_s") or 0), 2)}})
        print(r["id"], r["set"], r["category"], "OK" if recs[-1]["correct"] else "KO", [k for k, v in ok.items() if not v], f"{out.get('latency_s', 0)}s LLM" if used_llm else "sans LLM", flush=True)
    summ = {}
    for st in sorted({x["set"] for x in recs}):
        rs = [x for x in recs if x["set"] == st]
        summ[st] = {"n": len(rs), "correct": sum(x["correct"] for x in rs)}
    llm_t = [x["temps"]["llm_s"] for x in recs if x["llm_utilise"] and x["temps"]["llm_s"] is not None]
    res_all = {"pipeline": a.pipeline, "sets": a.sets, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "resume": summ,
               "exactitude": round(sum(x["correct"] for x in recs) / len(recs), 3),
               "temps_recherche_ms_moy": round(statistics.mean(x["temps"]["recherche_ms"] for x in recs), 1),
               "temps_llm_s_moy": round(statistics.mean(llm_t), 1) if llm_t else 0, "n_appels_llm": len(llm_t),
               "cache": _stats, "note": "Notation automatique ; jeux relus par un assistant IA, pas par un juriste humain.", "details": recs}
    dst = HERE / "results" / f"{a.tag or 'e2e_' + a.pipeline}.json"
    dst.write_text(json.dumps(res_all, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRÉSUMÉ", json.dumps(summ), "| exactitude", res_all["exactitude"], "| recherche moy", res_all["temps_recherche_ms_moy"], "ms | LLM moy",
          res_all["temps_llm_s_moy"], "s | cache", _stats)
    print("écrit :", dst)


main()
