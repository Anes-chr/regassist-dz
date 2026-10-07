"""Tableaux complémentaires du rapport de phase 3 (comparaison des pipelines sur le benchmark humain, relecture IA des échecs, re-mesure des jeux historiques, performances),
UNIQUEMENT à partir des fichiers mesurés sous agent_fr/eval/results/ et de ai_adjudication.json. Une cellule sans mesure affiche « non mesuré ».
Usage : python -m agent_fr.eval.human.make_tables3_extra > docs/tables_phase3_extra.md"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "agent_fr" / "eval" / "results"
HUMAN = ROOT / "agent_fr" / "eval" / "human"
PIPES = ("legacy", "bm25", "vector", "hybrid_plain", "hybrid", "hybrid_rerank")


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f3(v):
    return f"{v[0]:.3f}" if v and v[0] is not None else "non mesuré"


def frac(v):
    return f"{round(v[0] * v[1])}/{v[1]}" if v and v[0] is not None else "non mesuré"


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    keys = [("R@1", "R@1"), ("R@3", "R@3"), ("R@5", "R@5"), ("R@10", "R@10"), ("MRR", "MRR"), ("temporel@1", "Temporel@1"), ("juridique@1", "Juridique@1")]
    print("## Comparaison des moteurs de recherche (retrieval seul, sans LLM) sur le benchmark humain\n")
    print("Même corpus final, mêmes questions ; `hybrid_rerank` est le moteur évalué dans la suite du rapport. « Refus corrects » = hors corpus + hors sujet ; « clarif. » = questions ambiguës.\n")
    for sp in ("DEV", "TEST"):
        print(f"### {sp}\n")
        print("| Moteur | n | " + " | ".join(l for _, l in keys) + " | Refus corrects | Clarif. |\n|---|---:|" + "---:|" * (len(keys) + 2))
        for p in PIPES:
            s = load(RES / f"human_score_ret_{p}_{sp}.json")
            if not s:
                print(f"| {p} | non mesuré |" + " |" * (len(keys) + 2))
                continue
            g = s["global"]
            print(f"| {p} | {g['n_repondre']} | " + " | ".join(f3(g.get(k)) for k, _ in keys) + f" | {frac(g.get('refus_correct'))} | {frac(g.get('clarification_correcte'))} |")
        print()
    print("### Sensibilité : classement calculé sur la liste de production (k = 6) au lieu de k = 10 (`hybrid_rerank`)\n")
    print("| Split | R@1 (k=6 / k=10) | R@3 | R@5 | R@10 | MRR |\n|---|---:|---:|---:|---:|---:|")
    for sp in ("DEV", "TEST"):
        a, b = load(RES / f"human_score_ret6_hybrid_rerank_{sp}.json"), load(RES / f"human_score_ret_hybrid_rerank_{sp}.json")
        if a and b:
            print(f"| {sp} | " + " | ".join(f"{f3(a['global'].get(k))} / {f3(b['global'].get(k))}" for k in ("R@1", "R@3", "R@5", "R@10", "MRR")) + " |")
    print("\n(R@10 n'est pas défini sur une liste de 6 passages.)\n")

    def wilson(k, n, z=1.96):
        if not n:
            return "non mesuré"
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
        return f"{k}/{n} = {p:.3f} [{max(0, c - h):.3f} ; {min(1, c + h):.3f}]"

    print("## Incertitude statistique (intervalle de Wilson à 95 %)\n")
    print("Les effectifs sont petits (DEV 64 et TEST 42 questions à réponse attendue) : une différence de quelques points entre DEV et TEST n'est pas significative.\n")
    print("| Mesure | DEV | TEST |\n|---|---|---|")
    scs = {sp: load(RES / f) for sp, f in (("DEV", "human_score_dev_final2.json"), ("TEST", "human_score_test_final.json"))}
    for k, lab in (("R@5", "Recall@5"), ("reponse_correcte", "Réponse correcte (C1–C5)"), ("hallucination", "Hallucination (auto)"), ("refus_a_tort", "Refus à tort"),
                   ("erreur_temporelle_critique", "Erreur temporelle critique"), ("refus_correct", "Refus corrects (hors corpus + hors sujet)"), ("clarification_correcte", "Clarification (ambiguës)")):
        cells = []
        for sp in ("DEV", "TEST"):
            v = scs[sp]["global"].get(k) if scs[sp] else None
            cells.append(wilson(round(v[0] * v[1]), v[1]) if v and v[0] is not None else "non mesuré")
        print(f"| {lab} | {cells[0]} | {cells[1]} |")
    print()

    adj = load(HUMAN / "ai_adjudication.json")
    if adj:
        print("## Relecture IA (non humaine) des réponses rejetées par la notation automatique\n")
        print("Aucune règle de notation n'est modifiée ; ces tableaux documentent les causes d'échec et les divergences probables avec une évaluation humaine. "
              "Seules les réponses rejetées sont relues (asymétrie : borne haute de l'exactitude).\n")
        sc = {sp: load(RES / f) for sp, f in (("DEV", "human_score_dev_final2.json"), ("TEST", "human_score_test_final.json"))}
        labels = ("correcte", "correcte_avec_defaut", "a_arbitrer", "partielle", "incorrecte")
        print("| Split | Réponses correctes (auto) | Rejetées relues | " + " | ".join(labels) + " | Exactitude auto | Estimation IA (auto + correcte + avec défaut) | Estimation IA haute (+ à arbitrer) |\n|---|---:|---:|" + "---:|" * (len(labels) + 3))
        for sp in ("DEV", "TEST"):
            if not sc[sp]:
                continue
            rep = [x for x in sc[sp]["items"] if x["comportement"] == "repondre"]
            n, ok = len(rep), sum(1 for x in rep if x["reponse_correcte"])
            its = [i for i in adj["items"] if i["split"] == sp and next(x for x in sc[sp]["items"] if x["id"] == i["id"])["comportement"] == "repondre"]
            c = collections.Counter(i["ai"] for i in its)
            low = ok + c["correcte"] + c["correcte_avec_defaut"]
            high = low + c["a_arbitrer"]
            print(f"| {sp} | {ok}/{n} | {len(its)} | " + " | ".join(str(c[l]) for l in labels) + f" | {ok / n:.3f} | {low}/{n} = {low / n:.3f} | {high}/{n} = {high / n:.3f} |")
        print("\n### Causes des échecs relus\n")
        causes = adj["_causes"]
        print("| Cause | DEV | TEST | Définition |\n|---|---:|---:|---|")
        cnt = collections.defaultdict(collections.Counter)
        for i in adj["items"]:
            cnt[i["cause"]][i["split"]] += 1
        for k in sorted(cnt, key=lambda x: -(cnt[x]["DEV"] + cnt[x]["TEST"])):
            print(f"| {k} | {cnt[k]['DEV']} | {cnt[k]['TEST']} | {causes[k]} |")
        print()

    for p in ("hybrid_rerank", "legacy"):
        r = load(RES / f"regression_phase3_{p}.json")
        o = load(RES / f"retrieval_all_{p}.json")
        if r and o:
            if p == "hybrid_rerank":
                print("## Re-mesure des jeux historiques (gold_v2 … v5, 136 questions avec retrieval) sur le corpus final\n")
                print("Retrieval seul ; identifiants remappés par empreinte de fichier ; résultats **non strictement comparables** à ceux de la phase 2 (corpus différent) et jamais mélangés au benchmark humain.\n")
                print("| Moteur | Mesure | Phase 2 (corpus 2026-10-06) | Phase 3 (corpus final) |\n|---|---|---:|---:|")
            a, b = o["summary"]["TOUT"], r["summary"]["TOUT"]
            for k in ("R@1", "R@3", "R@5", "R@10", "MRR", "faux_refus", "refus_ok", "clarif_ok", "perime_en_tete"):
                print(f"| {p} | {k} | {a.get(k, 'non mesuré')} | {b.get(k, 'non mesuré')} |")
    print()
    abl, abl_h = load(RES / "human_score_abl_series_DEV.json"), load(RES / "regression_phase3_abl_series_hybrid_rerank.json")
    ref, ref_h = load(RES / "human_score_ret_hybrid_rerank_DEV.json"), load(RES / "regression_phase3_hybrid_rerank.json")
    wi = load(RES / "whatif_relations_regression_hybrid_rerank.json")
    if abl and abl_h and ref and ref_h:
        print("\n## Mesures d'ablation et de simulation (hors système évalué, retrieval seul)\n")
        print("Ces mesures documentent l'effet de la règle de séries (nouvelle en phase 3) et d'un défaut de relations du corpus (voir §1 du rapport). Elles ne modifient ni le moteur ni le corpus évalués.\n")
        print("| Mesure | Système évalué | Facteur de série désactivé | Relations repointées vers le document FR (simulation) |\n|---|---:|---:|---:|")
        for k, lab in (("R@1", "Jeux historiques R@1"), ("R@3", "Jeux historiques R@3"), ("R@5", "Jeux historiques R@5"), ("MRR", "Jeux historiques MRR")):
            w = wi["summary"]["TOUT"].get(k) if wi else "non mesuré"
            print(f"| {lab} (136 questions) | {ref_h['summary']['TOUT'].get(k)} | {abl_h['summary']['TOUT'].get(k)} | {w} |")
        for k, lab in (("R@1", "Benchmark humain DEV R@1"), ("R@3", "Benchmark humain DEV R@3"), ("R@5", "Benchmark humain DEV R@5"), ("MRR", "Benchmark humain DEV MRR"), ("juridique@1", "Benchmark humain DEV juridique@1")):
            wd = load(RES / "human_score_whatif_relations_DEV.json")
            print(f"| {lab} (64 questions) | {f3(ref['global'].get(k))} | {f3(abl['global'].get(k))} | {f3(wd['global'].get(k)) if wd else 'non mesuré'} |")
    pf = load(RES / "perf_phase3.json")
    p2 = load(RES / "perf_phase2.json")
    if pf:
        print("## Performances (machine : i7-13700, 24 threads, 15,6 Go de RAM, sans GPU, llama-server chargé)\n")
        print("| Mesure | Phase 2 | Phase 3 (corpus final) |\n|---|---:|---:|")
        rows = [("RSS agent après chargement (Mo)", lambda d: d["rss_mb"]["final"]), ("RSS llama-server (Mo)", lambda d: d["llama_server_rss_mb"]),
                ("retrieval hybrid_rerank, total moy. (ms)", lambda d: d["pipelines"]["hybrid_rerank"]["total_ms"]["moy"]),
                ("retrieval hybrid_rerank, total p95 (ms)", lambda d: d["pipelines"]["hybrid_rerank"]["total_ms"]["p95"]),
                ("  dont embedding question moy. (ms)", lambda d: d["pipelines"]["hybrid_rerank"]["embedding_ms"]["moy"]),
                ("  dont recherche BM25 + vecteurs moy. (ms)", lambda d: d["pipelines"]["hybrid_rerank"]["recherche_ms"]["moy"]),
                ("  dont reranking moy. (ms)", lambda d: d["pipelines"]["hybrid_rerank"]["reranking_ms"]["moy"]),
                ("retrieval hybrid (sans reranker), total moy. (ms)", lambda d: d["pipelines"]["hybrid"]["total_ms"]["moy"]),
                ("premier appel hybrid_rerank (s)", lambda d: d["premier_appel_s"]["hybrid_rerank"])]
        for lab, fn in rows:
            print(f"| {lab} | {fn(p2) if p2 else 'non mesuré'} | {fn(pf)} |")
    import statistics as st
    print("\n| Bout en bout (Qwen3-4B local, mesuré pendant les runs DEV/TEST) | n appels LLM | LLM moy. / médiane / p95 / max (s) | Total par question moy. / médiane / p95 (s) |\n|---|---:|---:|---:|")
    for lab, f in (("DEV (78 questions)", "human_bench_dev_final2.json"), ("TEST (52 questions)", "human_bench_test_final.json")):
        d = load(RES / f)
        if not d:
            continue
        lat = sorted(r["latency_llm_s"] for r in d["records"] if r.get("latency_llm_s"))
        tot = sorted(r["total_s"] for r in d["records"] if r.get("total_s"))
        q = lambda v, p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
        print(f"| {lab} | {len(lat)} | {st.mean(lat):.1f} / {st.median(lat):.1f} / {q(lat, .95):.1f} / {max(lat):.1f} | {st.mean(tot):.1f} / {st.median(tot):.1f} / {q(tot, .95):.1f} |")


if __name__ == "__main__":
    main()
