"""Tableaux Markdown du rapport de phase 3, UNIQUEMENT à partir des fichiers mesurés (results/human_score_*.json). Une cellule sans mesure affiche « non mesuré ».
Usage : python -m agent_fr.eval.human.make_tables3 --bench benchmark_v1.jsonl --scores dev=results/human_score_dev_final.json test=results/human_score_test_final.json > docs/tables_phase3.md"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEYS = [("R@1", "Recall@1"), ("R@3", "Recall@3"), ("R@5", "Recall@5"), ("R@10", "Recall@10"), ("MRR", "MRR"), ("doc@1", "Texte@1"), ("doc@5", "Texte@5"), ("article@1", "Article@1"),
        ("article@5", "Article@5"), ("temporel@1", "Exactitude temporelle@1"), ("juridique@1", "Exactitude juridique@1")]
ANS = [("retrieval_correct", "Retrieval correct (top-5)"), ("contexte_suffisant", "Contexte suffisant"), ("C1", "C1 répond (faits clés)"), ("C2", "C2 soutenue par les sources citées"),
       ("C3", "C3 bonne version"), ("C4", "C4 citation correcte"), ("C5", "C5 rien hors contexte"), ("reponse_correcte", "**Réponse correcte (C1–C5)**"), ("statut_correct", "Statut juridique correct"),
       ("hallucination", "Hallucination (auto)"), ("refus_a_tort", "Refus à tort"), ("erreur_temporelle_critique", "Erreur temporelle critique")]


def cell(v):
    if v is None or (isinstance(v, list) and v[0] is None):
        return "non mesuré"
    if isinstance(v, list):
        return f"{v[0]:.3f} ({round(v[0] * v[1])}/{v[1]})" if v[1] else "non mesuré"
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", nargs="+", required=True, help="nom=chemin")
    a = ap.parse_args()
    sc = {}
    for kv in a.scores:
        k, p = kv.split("=", 1)
        pth = Path(p) if Path(p).is_absolute() else ROOT / p
        sc[k] = json.loads(pth.read_text(encoding="utf-8")) if pth.exists() else None
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    names = list(sc)
    print("### Retrieval (questions à réponse attendue)\n")
    print("| Mesure | " + " | ".join(names) + " |\n|---|" + "---:|" * len(names))
    print("| n (questions à réponse attendue) | " + " | ".join(str(sc[n]["global"]["n_repondre"]) if sc[n] else "non mesuré" for n in names) + " |")
    for k, lab in KEYS:
        print(f"| {lab} | " + " | ".join(cell(sc[n]["global"].get(k)) if sc[n] else "non mesuré" for n in names) + " |")
    print("\n### Réponse finale (Qwen3-4B local)\n")
    print("| Mesure | " + " | ".join(names) + " |\n|---|" + "---:|" * len(names))
    for k, lab in ANS:
        print(f"| {lab} | " + " | ".join(cell(sc[n]["global"].get(k)) if sc[n] else "non mesuré" for n in names) + " |")
    print("\n### Refus, clarification, hors corpus\n")
    print("| Mesure | " + " | ".join(names) + " |\n|---|" + "---:|" * len(names))
    for k, lab in (("refus_correct", "Refus corrects (hors corpus + hors sujet)"), ("hors_corpus_repondu", "Question à refuser avec réponse"), ("clarification_correcte", "Clarification demandée (questions ambiguës)")):
        print(f"| {lab} | " + " | ".join(cell(sc[n]["global"].get(k)) if sc[n] else "non mesuré" for n in names) + " |")
    for n in names:
        if not sc[n]:
            continue
        print(f"\n### Par type de question — {n}\n")
        print("| Type | n | Recall@5 | MRR | Temporel@1 | Réponse correcte | Hallucination | Refus / clarif. |\n|---|---:|---:|---:|---:|---:|---:|---:|")
        for t, g in sc[n]["par_type"].items():
            rc = g.get("refus_correct")
            rf = cell(rc) if rc and rc[1] else cell(g.get("clarification_correcte"))
            print(f"| {t} | {g['n']} | {cell(g.get('R@5'))} | {cell(g.get('MRR'))} | {cell(g.get('temporel@1'))} | {cell(g.get('reponse_correcte') if g['n_repondre'] else g.get('reponse_correcte_toutes'))} | {cell(g.get('hallucination'))} | {rf} |")
        st = sc[n].get("sous_benchmark_temporalite")
        if st and st["n"]:
            print(f"\n**Sous-benchmark temporalité — {n}** (n = {st['n']}) : Recall@1 {cell(st.get('R@1'))} ; exactitude temporelle@1 {cell(st.get('temporel@1'))} ; exactitude juridique@1 {cell(st.get('juridique@1'))} ; "
                  f"réponse correcte {cell(st.get('reponse_correcte'))} ; statut correct {cell(st.get('statut_correct'))} ; erreurs temporelles critiques {cell(st.get('erreur_temporelle_critique'))}")


if __name__ == "__main__":
    main()
