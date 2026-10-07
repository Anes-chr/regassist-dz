"""Exécute le jeu AVEUGLE (agent_fr/eval/llm_blind) contre un llama-server et note automatiquement.
À utiliser pour comparer « Qwen3-4B de base » et toute future version (fine-tunée ou non) : même jeu, même consigne, température 0.
Usage : python llm_local/run_blind.py --tag base [--url http://127.0.0.1:8187]"""
import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
from llm_client import chat, health  # noqa: E402
from scoring import score  # noqa: E402
from agent_fr.answer import SYSTEM, NOT_FOUND, ABSENCE  # noqa: E402  (consigne EXACTE de l'agent)
from agent_fr.llm_backends import SCHEMA  # noqa: E402

BLIND = ROOT / "agent_fr" / "eval" / "llm_blind" / "llm_blind_set.jsonl"
NORMALIZE = False   # activé par --normalize : applique la normalisation de refus de l'agent (système = modèle + post-traitement)
REFUSAL_MARKERS = ["je ne trouve pas", "dispositions correspondantes", "لا أجد", "لا توجد", "لا يوجد", "غير متوفر", "لا تتوفر", "لا يمكنني"]


def norm(s):
    return " ".join(str(s).replace("’", "'").lower().split())


def source_block(ctx):
    meta = (f"texte={ctx['texte']} | titre={ctx['texte']} | article={ctx['article']} | page={ctx['page']} | "
            f"statut={ctx['statut']} | relations={{}}")
    return f"<source id=\"S1\">\n[{meta}]\n{ctx['passage'].replace('<', '‹').replace('>', '›')}\n</source>"


def parse_json(t):
    m = re.search(r"\{.*\}", t, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def judge_grounded(it, text):
    d = parse_json(text)
    if d is None:
        return False, ["JSON invalide"]
    fails = []
    ans = str(d.get("answer", ""))
    found = bool(d.get("found", False))
    cites = d.get("citations", []) or []
    if it["expect_found"]:
        if not found:
            fails.append("a refusé alors que la réponse était dans la source")
        if norm(it["key_fact"]) not in norm(ans):
            fails.append("fait clé absent de la réponse")
        if it.get("expect_cite") not in cites:
            fails.append("citation [S1] absente")
    else:
        refused = (not found) or any(m in norm(ans) for m in REFUSAL_MARKERS) or (NORMALIZE and bool(ABSENCE.search(ans)))   # refus normalisé par le système
        if not refused:
            fails.append("a répondu alors que la source ne contient pas l'information (invention probable)")
        if found and cites:
            fails.append("found=true avec citations sur une question sans réponse")
    return (not fails), fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8187")
    ap.add_argument("--tag", default="base")
    ap.add_argument("--max-tokens", type=int, default=500)
    ap.add_argument("--schema", action="store_true", help="décodage contraint par schéma JSON (comme l'agent)")
    ap.add_argument("--normalize", action="store_true", help="applique la normalisation de refus de l'agent")
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if not health(a.url):
        sys.exit("llama-server ne répond pas")
    global NORMALIZE
    NORMALIZE = a.normalize
    items = [json.loads(l) for l in open(BLIND, encoding="utf-8") if l.strip()]
    rows = []
    for it in items:
        if it["cat"] in ("cite", "unknown"):
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Question : {it['question']}\n\n{source_block(it['context'])}"}]
            res = chat(msgs, url=a.url, max_tokens=a.max_tokens, json_mode=True, schema=SCHEMA if a.schema else None)
            ok, fails = judge_grounded(it, res["text"])
        else:
            res = chat([{"role": "user", "content": it["prompt"]}], url=a.url, max_tokens=a.max_tokens)
            ok, fails = score(it, res["text"])
        rows.append({"id": it["id"], "cat": it["cat"], "ok": ok, "fails": fails, "answer": res["text"],
                     **{k: v for k, v in res.items() if k != "text"}})
        print(f"{it['id']} {it['cat']:7} {'OK ' if ok else 'KO '} total={res['total_s']}s gen={res['gen_tok_s']}t/s {'; '.join(fails)}", flush=True)
    summ = {}
    for c in sorted({r["cat"] for r in rows}):
        rs = [r for r in rows if r["cat"] == c]
        summ[c] = f"{sum(r['ok'] for r in rs)}/{len(rs)}"
    man = json.loads((BLIND.parent / "manifest.json").read_text(encoding="utf-8"))
    out = {"tag": a.tag, "set_sha256": man["set_sha256"], "date": time.strftime("%Y-%m-%d %H:%M:%S"), "set": "agent_fr/eval/llm_blind (40 items, 5 catégories)",
           "score_auto": summ, "total_ok": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
           "latence_mediane_s": statistics.median(r["total_s"] for r in rows),
           "latence_mediane_cite_unknown_s": statistics.median([r["total_s"] for r in rows if r["cat"] in ("cite", "unknown")] or [0]),
           "note": "Notation automatique par règles : elle détecte des défauts probables, elle ne remplace pas une relecture humaine.",
           "details": rows}
    dst = Path(__file__).resolve().parent / "results" / f"blind_{a.tag}.json"
    dst.parent.mkdir(exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Jeu aveugle", a.tag, summ, "total", out["total_ok"], "| latence médiane", out["latence_mediane_s"], "s")
    print("écrit :", dst)


main()
