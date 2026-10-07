"""Re-mesure des jeux HISTORIQUES (gold_v2 … gold_v5, Phase 2) sur le corpus de la PHASE 4, en retrieval seul (aucun LLM).

Pourquoi : montrer que les corrections de corpus de la phase 4 (jumeaux FR/AR, identifiants de chunks, dates) n'ont pas dégradé la recherche sur les jeux déjà connus.
Les identifiants de textes (work_id) ont changé pour une partie du corpus : on les remappe de l'ancien instantané (corpus_2026-10-06) vers le nouveau par l'empreinte du fichier
source (file_hash), jamais par heuristique. Un item dont un texte attendu n'existe plus sous aucun identifiant est écarté et listé.
Les fichiers gold_v*.jsonl d'origine ne sont PAS modifiés ; les copies remappées sont écrites sous agent_fr/eval/regression_phase4/.
Ces résultats ne sont PAS comparables strictement à ceux de la phase 2 (corpus différent) et ne se mélangent jamais avec le benchmark humain.
Usage : AGENT_CORPUS_DIR=<instantané final> python -m agent_fr.eval.regression_phase4 --pipelines hybrid_rerank legacy"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = Path("D:/llm/snapshots/corpus_2026-10-06")
OUT = HERE / "regression_phase4"
RES = HERE / "results"


def docs(base):
    out = []
    for lg in ("fr", "ar", "und"):
        p = base / f"documents_{lg}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            out += d if isinstance(d, list) else list(d.values())
    return out


def build_map(new_dir):
    old, new = docs(OLD), docs(Path(new_dir))
    by_hash = {}
    for d in new:
        if d.get("file_hash"):
            by_hash.setdefault(d["file_hash"], set()).add(d["work_id"])
    mapping, ambiguous, missing = {}, {}, set()
    for d in old:
        w = d["work_id"]
        news = by_hash.get(d.get("file_hash"), set())
        if len(news) == 1:
            mapping.setdefault(w, set()).add(next(iter(news)))
        elif len(news) > 1:
            ambiguous[w] = sorted(news)
        else:
            missing.add(w)
    return {w: sorted(v) for w, v in mapping.items()}, ambiguous, missing


def remap_gold(sets, mapping):
    OUT.mkdir(exist_ok=True)
    report = {"remappes": 0, "inchanges": 0, "ecartes": []}
    for s in sets:
        rows = [json.loads(l) for l in open(HERE / f"gold_{s}.jsonl", encoding="utf-8") if l.strip()]
        kept = []
        for r in rows:
            ok = True
            for key in ("expected", "stale_top1"):
                v = r.get(key)
                if not v:
                    continue
                if key == "expected":
                    for e in v:
                        m = mapping.get(e["work_id"])
                        if not m:
                            ok = False
                            break
                        if len(m) > 1:
                            ok = False
                            break
                        if m[0] != e["work_id"]:
                            report["remappes"] += 1
                        else:
                            report["inchanges"] += 1
                        e["work_id"] = m[0]
                else:
                    r[key] = [mapping.get(w, [w])[0] for w in v]
            if ok:
                kept.append(r)
            else:
                report["ecartes"].append({"set": s, "id": r["id"], "question": r["question"][:90]})
        (OUT / f"gold_{s}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in kept) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipelines", nargs="+", default=["hybrid_rerank", "legacy"])
    ap.add_argument("--sets", default="v2,v3,v4,v5")
    a = ap.parse_args()
    new_dir = os.environ.get("AGENT_CORPUS_DIR")
    if not new_dir:
        sys.exit("AGENT_CORPUS_DIR (instantané final) est obligatoire")
    sets = tuple(a.sets.split(","))
    mapping, ambiguous, missing = build_map(new_dir)
    rep = remap_gold(sets, mapping)
    rep.update({"textes_anciens": len(mapping) + len(ambiguous) + len(missing), "textes_remappes_uniquement": len(mapping), "ambigus": ambiguous, "disparus": sorted(missing)})
    (RES / "regression_phase4_remap.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("remap :", {k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in rep.items()})
    from agent_fr.eval import retrieval_eval as RE
    RE.HERE = OUT                                           # les copies remappées
    for p in a.pipelines:
        recs = RE.evaluate(p, sets)
        summ = RE.summarize(recs)
        dst = RES / f"regression_phase4_{p}.json"
        dst.write_text(json.dumps({"pipeline": p, "tag": f"regression_phase4_{p}", "date": time.strftime("%Y-%m-%d %H:%M:%S"), "corpus": new_dir, "summary": summ, "records": recs},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(p, json.dumps(summ["TOUT"], ensure_ascii=False))


if __name__ == "__main__":
    main()
