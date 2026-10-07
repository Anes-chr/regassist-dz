"""Génère les tableaux comparatifs (Markdown) UNIQUEMENT à partir des fichiers de résultats mesurés (agent_fr/eval/results/*.json).
Une cellule dont le fichier de mesure n'existe pas affiche « non mesuré » : jamais d'estimation présentée comme une mesure.
Usage : python -m agent_fr.eval.make_tables > docs/tables_phase2.md"""
import json
import sys
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"
ORDER = [("legacy", "Recherche actuelle (BM25 + règles, avant phase 2)"), ("bm25", "BM25 pur"), ("vector", "Vectorielle pure (e5-small)"),
         ("hybrid_plain", "Hybride simple (BM25 + vecteurs, RRF)"), ("hybrid", "Hybride + logique juridique (temps, versions, refus)"),
         ("hybrid_rerank", "Hybride + logique juridique + reranker")]
E2E_TAG = "e2e_{}_v345"            # bout en bout : jeux v3 + v4 + v5 (Qwen3-4B local)
ALL_TAG = "retrieval_all_{}.json"  # retrieval, moteur final, jeux v2 + v3 + v4 + v5 (une seule passe, machine au repos)
OLD_TAG = "retrieval_final_{}.json"  # retrieval v2 + v3 + v4 (avant ajout de v5 et de la correction des qualificatifs génériques)
V5_TAG = "retrieval_v5_{}.json"    # PREMIÈRE passe sur le jeu vierge v5 (avant la correction des qualificatifs génériques)


def load(p):
    f = RES / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def retrieval_table(pattern, key="TOUT", label=""):
    print(f"\n### Retrieval — {label}\n")
    print("| Pipeline | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | R@5 (successeur accepté) | Refus corrects | Faux refus (questions valides) | Clarif. | Texte périmé en tête | Recherche (ms/question) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, lab in ORDER:
        d = load(pattern.format(name))
        if not d or key not in d["summary"]:
            print(f"| {lab} | non mesuré | | | | | | | | | | | |")
            continue
        s = d["summary"][key]
        print(f"| {lab} | {s.get('n')} | {s.get('R@1')} | {s.get('R@3')} | {s.get('R@5')} | {s.get('R@10')} | {s.get('MRR')} | {s.get('R@5s')} | "
              f"{s.get('refus_ok', '—')} | {s.get('faux_refus', '—')} | {s.get('clarif_ok', '—')} | {s.get('perime_en_tete', '—')} | {s.get('search_ms_moy')} |")


def category_table(pattern=ALL_TAG, pipelines=("legacy", "bm25", "vector", "hybrid_plain", "hybrid", "hybrid_rerank")):
    data = {}
    for p in pipelines:
        d = load(pattern.format(p))
        if d:
            data[p] = d["summary"]
    if not data:
        return
    cats = sorted({k for s in data.values() for k in s if k.startswith("cat:")})
    print("\n### Retrieval par catégorie (MRR ; n = questions avec passage attendu)\n")
    print("| Catégorie | n | " + " | ".join(pipelines) + " |")
    print("|---|---:|" + "---:|" * len(pipelines))
    for c in cats:
        n = next((data[p][c].get("n") for p in data if data[p].get(c) and data[p][c].get("n")), 0)
        if not n:
            continue
        print(f"| {c[4:]} | {n} | " + " | ".join(str(data[p].get(c, {}).get("MRR", "—")) for p in pipelines) + " |")
    print("\n### Refus et clarifications par catégorie (corrects / total)\n")
    print("| Catégorie | " + " | ".join(pipelines) + " |")
    print("|---|" + "---:|" * len(pipelines))
    for c in cats:
        rows = [data[p].get(c, {}) for p in pipelines]
        key = "refus_ok" if any("refus_ok" in r for r in rows) else ("clarif_ok" if any("clarif_ok" in r for r in rows) else None)
        if key:
            print(f"| {c[4:]} | " + " | ".join(str(r.get(key, "—")) for r in rows) + " |")


def e2e_data():
    out = {}
    for name, _ in ORDER:
        d = load(E2E_TAG.format(name) + ".json")
        if d:
            out[name] = d
    return out


def e2e_table():
    print("\n### Bout en bout (recherche + Qwen3-4B local) — jeux v3 + v4 + v5\n")
    print("| Pipeline | Exactitude finale | v3 | v4 | v5 (vierge) | Recherche moy. | LLM moy. (par appel) | Total moyen / question |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, lab in ORDER:
        d = load(E2E_TAG.format(name) + ".json")
        if not d:
            print(f"| {lab} | non mesuré | | | | | | |")
            continue
        n = sum(v["n"] for v in d["resume"].values())
        c = sum(v["correct"] for v in d["resume"].values())
        det = d["details"]
        tot = sum(x["temps"]["total_s"] for x in det) / len(det)
        per = " | ".join(f"{d['resume'][s]['correct']}/{d['resume'][s]['n']}" if s in d["resume"] else "—" for s in ("v3", "v4", "v5"))
        print(f"| {lab} | {d['exactitude']} ({c}/{n}) | {per} | {d['temps_recherche_ms_moy']} ms | {d['temps_llm_s_moy']} s | {tot:.1f} s |")


def e2e_by_category():
    data = e2e_data()
    if not data:
        return
    cats = sorted({x["category"] for d in data.values() for x in d["details"]})
    names = [n for n, _ in ORDER if n in data]
    print("\n### Bout en bout par catégorie (réponses correctes / questions)\n")
    print("| Catégorie | " + " | ".join(names) + " |")
    print("|---|" + "---:|" * len(names))
    for c in cats:
        cells = []
        for n in names:
            rs = [x for x in data[n]["details"] if x["category"] == c]
            cells.append(f"{sum(x['correct'] for x in rs)}/{len(rs)}" if rs else "—")
        print(f"| {c} | " + " | ".join(cells) + " |")


def adjudication_table():
    d = load("e2e_adjudication.json")
    if not d:
        return
    print("\n### Bout en bout — notation automatique et relecture IA des échecs (PAS une relecture par un juriste humain)\n")
    print("| Pipeline | Auto (strict, littéral) | Après relecture IA | Récupérés (faux négatifs de notation) | Rétrogradés (faux positifs) |")
    print("|---|---:|---:|---|---|")
    for name, lab in ORDER:
        p = d["pipelines"].get(name)
        if p:
            print(f"| {lab} | {p['auto']}/{p['n']} ({p['auto'] / p['n']:.3f}) | {p['relu']}/{p['n']} ({p['relu'] / p['n']:.3f}) | {', '.join(p['recuperes'])} | {', '.join(p['retrogrades']) or '—'} |")
    print("\nRègles de relecture :`agent_fr/eval/adjudicate.py` (preuve vérifiée mécaniquement dans les passages cités ; rétrogradation mécanique des listes incomplètes et des réponses hésitantes).")


def mandatory_table():
    """Tableau exigé par la consigne : Pipeline | Recall@5 | MRR | Exactitude finale | Temps moyen."""
    print("\n### Tableau de comparaison exigé (retrieval : 136 questions v2+v3+v4+v5 ; exactitude finale : v3+v4+v5 avec Qwen3-4B local)\n")
    print("| Pipeline | Recall@5 | MRR | Exactitude finale | Temps moyen (recherche seule) | Temps moyen (bout en bout, LLM inclus) |")
    print("|---|---:|---:|---:|---:|---:|")
    e2e = e2e_data()
    for name, lab in ORDER:
        d = load(ALL_TAG.format(name))
        if not d:
            print(f"| {lab} | non mesuré | non mesuré | non mesuré | non mesuré | non mesuré |")
            continue
        s = d["summary"]["TOUT"]
        if name in e2e:
            det = e2e[name]["details"]
            n = len(det)
            ex = f"{e2e[name]['exactitude']} ({sum(x['correct'] for x in det)}/{n})"
            tot = f"{sum(x['temps']['total_s'] for x in det) / n:.1f} s"
        else:
            ex, tot = "non mesuré", "non mesuré"
        print(f"| {lab} | {s.get('R@5')} | {s.get('MRR')} | {ex} | {s.get('search_ms_moy')} ms | {tot} |")


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    mandatory_table()
    retrieval_table(ALL_TAG, "TOUT", "moteur final, 136 questions (v2 + v3 + v4 + v5), une passe, machine au repos")
    retrieval_table(V5_TAG, "TOUT", "jeu VIERGE v5 — PREMIÈRE passe (avant correction des qualificatifs génériques ; ranking inchangé par cette correction)")
    retrieval_table(OLD_TAG, "TOUT", "v2 + v3 + v4 (100 questions ; v3 et v4 consultés pour corriger des bogues)")
    retrieval_table(OLD_TAG, "v4/v4", "jeu v4 (écrit après le réglage des seuils, avant la résolution de versions)")
    category_table()
    e2e_table()
    adjudication_table()
    e2e_by_category()
