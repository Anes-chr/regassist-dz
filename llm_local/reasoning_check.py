"""Les réponses « étape par étape » dépassent 450 tokens : on les relance avec une limite plus large pour distinguer
un raisonnement faux d'une réponse simplement coupée. Usage : python llm_local/reasoning_check.py [--runs 3] [--max-tokens 1200]"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat, health  # noqa: E402
from scoring import score  # noqa: E402

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--runs", type=int, default=3)
ap.add_argument("--max-tokens", type=int, default=1200)
a = ap.parse_args()
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if not health():
    sys.exit("llama-server ne répond pas")
items = [json.loads(l) for l in open(HERE / "bench_prompts.jsonl", encoding="utf-8") if l.strip()]
out = []
for it in [i for i in items if i["cat"] == "raison"]:
    for r in range(a.runs):
        res = chat([{"role": "user", "content": it["prompt"]}], max_tokens=a.max_tokens)
        ok, fails = score(it, res["text"])
        truncated = res["gen_n"] is not None and res["gen_n"] >= a.max_tokens - 2
        out.append({"id": it["id"], "run": r + 1, "ok": ok, "fails": fails, "tokens": res["gen_n"], "truncated": truncated,
                    "total_s": res["total_s"], "answer": res["text"]})
        print(it["id"], f"run{r + 1}", "OK" if ok else "KO", f"{res['gen_n']} tok", f"{res['total_s']}s", "TRONQUÉ" if truncated else "", "; ".join(fails), flush=True)
(HERE / "results" / "reasoning_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("RÉSUMÉ", {i: f"{sum(o['ok'] for o in out if o['id'] == i)}/{sum(1 for o in out if o['id'] == i)}" for i in sorted({o['id'] for o in out})})
