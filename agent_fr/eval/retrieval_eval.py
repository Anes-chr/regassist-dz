"""Évaluation du RETRIEVAL seul (avant le LLM), sur gold_v2 + gold_v3, avec enregistrement question par question.

Métriques : Recall@1/3/5/10, MRR (items avec passage attendu ; pour les items « multi », TOUS les passages attendus doivent être retrouvés),
refus corrects (hors corpus / hors sujet), clarifications (ambigu), « texte périmé en 1re position » (temporel), temps de recherche.
Usage : python -m agent_fr.eval.retrieval_eval --pipeline legacy --tag baseline_legacy [--sets v2,v3]
Le corpus évalué est l'INSTANTANÉ figé (AGENT_CORPUS_DIR par défaut : D:/llm/snapshots/corpus_2026-10-06)."""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

os.environ.setdefault("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06")
from agent_fr.agent import get_index  # noqa: E402
from agent_fr.pipelines import get_pipeline  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
KS = (1, 3, 5, 10)


def load(sets):
    rows = []
    for s in sets:
        for l in open(HERE / f"gold_{s}.jsonl", encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                r["set"] = s
                rows.append(r)
    return rows


def ranking(hits):
    seen, out = set(), []
    for h in hits:
        c = h.chunk
        key = (c["work_id"], c.get("article"))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def match(c, e):
    return c["work_id"] == e["work_id"] and (e["article"] is None or c.get("article") == e["article"])


def successors(idx):
    """work_id -> ensemble des work_id des textes qui le modifient / complètent / abrogent / remplacent (successeurs légitimes)."""
    out = {}
    for d in idx.docs.values():
        for key in ("modifie_par", "complete_par", "abroge_par", "remplace_par"):
            for e in d.get(key, []):
                if e.get("work_id"):
                    out.setdefault(d["work_id"], set()).add(e["work_id"])
    return out


def evaluate(pipeline_name, sets=("v2", "v3"), k=10, verbose=True):
    idx = get_index()
    succ = successors(idx)
    search = get_pipeline(pipeline_name)
    rows = load(sets)
    recs = []
    for r in rows:
        t0 = time.perf_counter()
        res = search(idx, r["question"], k)
        ms = (time.perf_counter() - t0) * 1000
        rk = ranking(res.hits)
        rec = {"id": r["id"], "set": r["set"], "split": r.get("split"), "category": r["category"], "question": r["question"],
               "found": res.found, "reason": res.reason, "clarify": bool(getattr(res, "clarify", False)), "search_ms": round(ms, 1),
               "retrieved": [{"chunk_id": c["chunk_id"], "work_id": c["work_id"], "article": c.get("article"), "date": c.get("date"),
                              "language": c.get("language"), "score": round(h.score, 4), "via": h.via}
                             for c, h in zip(rk, [next(h for h in res.hits if h.chunk is c) for c in rk])][:k]}
        if r.get("expect_refuse"):
            rec["ok_refus"] = not res.found
        elif r.get("expect_clarify"):
            rec["ok_clarify"] = bool(getattr(res, "clarify", False))
        else:
            exp = r["expected"]
            positions = []
            for e in exp:
                p = next((i + 1 for i, c in enumerate(rk) if match(c, e)), None)
                positions.append(p)
            if r.get("mode") == "all":
                rank = max(positions) if all(p for p in positions) else None
            else:
                got = [p for p in positions if p]
                rank = min(got) if got else None
            rec["rank"] = rank
            rec["positions"] = positions
            # variante « successeur légitime accepté » (jamais pour les questions historiques : un texte postérieur y est périmé)
            if r["category"] != "historique" and r.get("mode") != "all":
                allowed = {e["work_id"] for e in exp} | {w for e in exp for w in succ.get(e["work_id"], ())}
                rs = next((i + 1 for i, c in enumerate(rk) if match(c, exp[0]) or c["work_id"] in allowed), None)
                rec["rank_succ"] = rs if rs and (rank is None or rs < rank) else rank
            else:
                rec["rank_succ"] = rank
            if r.get("stale_top1") is not None and rk:
                rec["stale_top1"] = rk[0]["work_id"] in r["stale_top1"]
            rec["top1"] = f'{rk[0]["work_id"]} art.{rk[0].get("article")}' if rk else None
        recs.append(rec)
    return recs


def summarize(recs):
    def agg(rs):
        ranked = [x for x in rs if "rank" in x]
        out = {"n": len(ranked)}
        if ranked:
            for kk in KS:
                out[f"R@{kk}"] = round(sum(1 for x in ranked if x["rank"] and x["rank"] <= kk) / len(ranked), 3)
            out["MRR"] = round(sum(1 / x["rank"] for x in ranked if x["rank"]) / len(ranked), 3)
            out["R@1s"] = round(sum(1 for x in ranked if x.get("rank_succ") and x["rank_succ"] <= 1) / len(ranked), 3)
            out["R@5s"] = round(sum(1 for x in ranked if x.get("rank_succ") and x["rank_succ"] <= 5) / len(ranked), 3)
            out["faux_refus"] = f"{sum(1 for x in ranked if not x['found'] and not x['clarify'])}/{len(ranked)}"      # question valide refusée par le moteur de recherche
            out["MRRs"] = round(sum(1 / x["rank_succ"] for x in ranked if x.get("rank_succ")) / len(ranked), 3)
        ref = [x for x in rs if "ok_refus" in x]
        if ref:
            out["refus_ok"] = f"{sum(x['ok_refus'] for x in ref)}/{len(ref)}"
        cl = [x for x in rs if "ok_clarify" in x]
        if cl:
            out["clarif_ok"] = f"{sum(x['ok_clarify'] for x in cl)}/{len(cl)}"
        st = [x for x in rs if "stale_top1" in x]
        if st:
            out["perime_en_tete"] = f"{sum(x['stale_top1'] for x in st)}/{len(st)}"
        out["search_ms_moy"] = round(statistics.mean(x["search_ms"] for x in rs), 1) if rs else None
        return out
    res = {"TOUT": agg(recs)}
    for key in sorted({(x["set"], x["split"]) for x in recs}, key=str):
        res[f"{key[0]}/{key[1]}"] = agg([x for x in recs if (x["set"], x["split"]) == key])
    for cat in sorted({x["category"] for x in recs}):
        res[f"cat:{cat}"] = agg([x for x in recs if x["category"] == cat])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="legacy")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--sets", default="v2,v3,v4")
    a = ap.parse_args()
    recs = evaluate(a.pipeline, tuple(a.sets.split(",")))
    summ = summarize(recs)
    RES.mkdir(exist_ok=True)
    tag = a.tag or a.pipeline
    (RES / f"retrieval_{tag}.json").write_text(json.dumps({"pipeline": a.pipeline, "tag": tag, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                           "corpus": os.environ["AGENT_CORPUS_DIR"], "summary": summ, "records": recs},
                                                          ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in summ.items():
        print(f"{k:34}", json.dumps(v, ensure_ascii=False))
    print("écrit :", RES / f"retrieval_{tag}.json")


if __name__ == "__main__":
    main()
