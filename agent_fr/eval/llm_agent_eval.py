"""Évalue l'AGENT COMPLET (recherche + LLM local) sur gold_v2 : l'agent répond-il juste, cite-t-il, refuse-t-il, en combien de temps ?
Notation automatique : fait clé présent dans la réponse rédigée, source attendue citée, refus corrects. Ne remplace pas une relecture humaine.
Usage (serveur local démarré) : python -m agent_fr.eval.llm_agent_eval [--tag base] [--limit N]"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

os.environ["AGENT_LLM"] = "local"
from agent_fr.agent import ask  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def norm(s):
    return " ".join(str(s).replace("’", "'").lower().split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="base_qwen3-4b")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(HERE / "gold_v2.jsonl", encoding="utf-8") if l.strip()]
    if a.limit:
        rows = rows[:a.limit]
    res = []
    for r in rows:
        t0 = time.time()
        out = ask(r["question"], use_llm=True)
        dt = round(time.time() - t0, 1)
        ok = {}
        used_llm = out.get("mode") == "llm"
        if r.get("expect_refuse"):
            ok["refus"] = not out["found"]
        else:
            exp = r["expected"]
            cited = [c for c in out["citations"]
                     if any(c["chunk_id"].split("::")[0].rsplit(".", 1)[0] == e["work_id"] and (e["article"] is None or str(c["article"]) == e["article"]) for e in exp)]
            ok["source_attendue_citee"] = bool(cited)
            if r.get("key_fact"):
                ok["fait_cle_dans_reponse"] = out["found"] and norm(r["key_fact"]) in norm(out["answer"])
            if r.get("expect_note_contains"):
                ok["avertissement_vigueur"] = any(r["expect_note_contains"] in n for n in out["notes"])
        res.append({"id": r["id"], "split": r["split"], "category": r["category"], "question": r["question"], "ok": ok, "mode": out.get("mode"),
                    "llm_utilise": used_llm, "latence_s": dt, "timings": out.get("llm_timings"), "reponse": out["answer"][:600],
                    "notes": out.get("notes", [])})
        print(r["id"], r["split"], r["category"], "OK" if all(ok.values()) else "KO", [k for k, v in ok.items() if not v], f"{dt}s", "LLM" if used_llm else "extractif", flush=True)
    summ = {}
    for sp in ("dev", "test", "holdout"):
        rs = [x for x in res if x["split"] == sp]
        if rs:
            keys = sorted({k for x in rs for k in x["ok"]})
            summ[sp] = {k: f"{sum(1 for x in rs if x['ok'].get(k))}/{sum(1 for x in rs if k in x['ok'])}" for k in keys}
    lat = [x["latence_s"] for x in res if x["llm_utilise"]]
    out = {"tag": a.tag, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "resume": summ,
           "latence_llm_mediane_s": statistics.median(lat) if lat else None, "latence_llm_max_s": max(lat) if lat else None,
           "n_llm": len(lat), "n_total": len(res),
           "note": "Notation automatique ; jeu relu par un assistant IA, pas par un juriste humain.", "details": res}
    dst = ROOT / "llm_local" / "results" / f"agent_llm_{a.tag}.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRÉSUMÉ", json.dumps(summ, ensure_ascii=False), "| latence LLM médiane", out["latence_llm_mediane_s"], "s, max", out["latence_llm_max_s"])
    print("écrit :", dst)


main()
