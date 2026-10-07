"""Baseline locale reproductible : 22 prompts (FR, AR, technique, instructions, raisonnement) contre llama-server.
Ce n'est PAS un benchmark scientifique : c'est un contrôle de bon fonctionnement et un point de départ comparable.
Usage : python llm_local/bench_quality.py [--url http://127.0.0.1:8187] [--runs 2] [--tag base]"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat, health  # noqa: E402
from scoring import score  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8187")
    ap.add_argument("--runs", type=int, default=2, help="répétitions par prompt (température 0 : sert à vérifier la stabilité)")
    ap.add_argument("--tag", default="base")
    ap.add_argument("--max-tokens", type=int, default=450)
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if not health(a.url):
        sys.exit("llama-server ne répond pas : lancez llm_local\\start_server.ps1")
    items = [json.loads(l) for l in open(HERE / "bench_prompts.jsonl", encoding="utf-8") if l.strip()]
    rows = []
    for it in items:
        for r in range(a.runs):
            res = chat([{"role": "user", "content": it["prompt"]}], url=a.url, max_tokens=a.max_tokens)
            ok, fails = score(it, res["text"])
            rows.append({"id": it["id"], "cat": it["cat"], "run": r + 1, "ok": ok, "fails": fails, **{k: v for k, v in res.items() if k != "text"},
                         "answer": res["text"]})
            print(f"{it['id']:4} run{r + 1} {'OK ' if ok else 'KO '} ttft={res['ttft_s']}s total={res['total_s']}s gen={res['gen_tok_s']} t/s "
                  f"({res['gen_n']} tok) {'; '.join(fails)}", flush=True)
    summary = {}
    for cat in sorted({r["cat"] for r in rows}):
        rs = [r for r in rows if r["cat"] == cat]
        summary[cat] = {"ok": sum(r["ok"] for r in rs), "n": len(rs)}
    # stabilité : mêmes réponses entre répétitions (température 0)
    stable = sum(1 for it in items if len({r["answer"] for r in rows if r["id"] == it["id"]}) == 1)
    gens = [r["gen_tok_s"] for r in rows if r["gen_tok_s"]]
    prom = [r["prompt_tok_s"] for r in rows if r["prompt_tok_s"] and (r["prompt_n"] or 0) > 20]
    out = {"tag": a.tag, "date": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": a.runs, "par_categorie": summary,
           "reponses_identiques_entre_runs": f"{stable}/{len(items)}",
           "gen_tok_s_median": statistics.median(gens) if gens else None, "prompt_tok_s_median": statistics.median(prom) if prom else None,
           "ttft_s_median": statistics.median([r["ttft_s"] for r in rows if r["ttft_s"]]), "total_s_median": statistics.median(r["total_s"] for r in rows),
           "rss_mb_max": max([r["rss_mb"] for r in rows if r["rss_mb"]] or [0]), "details": rows}
    dst = HERE / "results" / f"bench_quality_{a.tag}.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Résumé", {k: f"{v['ok']}/{v['n']}" for k, v in summary.items()}, "| stabilité", out["reponses_identiques_entre_runs"],
          "| gen médiane", out["gen_tok_s_median"], "t/s | RAM serveur max", out["rss_mb_max"], "Mo")
    print("écrit :", dst)


main()
