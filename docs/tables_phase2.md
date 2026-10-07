
### Tableau de comparaison exigé (retrieval : 136 questions v2+v3+v4+v5 ; exactitude finale : v3+v4+v5 avec Qwen3-4B local)

| Pipeline | Recall@5 | MRR | Exactitude finale | Temps moyen (recherche seule) | Temps moyen (bout en bout, LLM inclus) |
|---|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 0.765 | 0.638 | 0.589 (66/112) | 1.9 ms | 28.8 s |
| BM25 pur | 0.706 | 0.587 | non mesuré | 2.2 ms | non mesuré |
| Vectorielle pure (e5-small) | 0.757 | 0.646 | non mesuré | 11.9 ms | non mesuré |
| Hybride simple (BM25 + vecteurs, RRF) | 0.838 | 0.688 | non mesuré | 14.0 ms | non mesuré |
| Hybride + logique juridique (temps, versions, refus) | 0.86 | 0.726 | 0.795 (89/112) | 13.6 ms | 20.0 s |
| Hybride + logique juridique + reranker | 0.89 | 0.77 | 0.857 (96/112) | 1038.5 ms | 23.7 s |

### Retrieval — moteur final, 136 questions (v2 + v3 + v4 + v5), une passe, machine au repos

| Pipeline | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | R@5 (successeur accepté) | Refus corrects | Faux refus (questions valides) | Clarif. | Texte périmé en tête | Recherche (ms/question) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 136 | 0.522 | 0.728 | 0.765 | 0.868 | 0.638 | 0.801 | 20/30 | 11/136 | 0/8 | 5/28 | 1.9 |
| BM25 pur | 136 | 0.478 | 0.654 | 0.706 | 0.824 | 0.587 | 0.75 | 15/30 | 14/136 | 0/8 | 5/28 | 2.2 |
| Vectorielle pure (e5-small) | 136 | 0.566 | 0.728 | 0.757 | 0.824 | 0.646 | 0.794 | 26/30 | 7/136 | 0/8 | 8/28 | 11.9 |
| Hybride simple (BM25 + vecteurs, RRF) | 136 | 0.581 | 0.772 | 0.838 | 0.882 | 0.688 | 0.86 | 26/30 | 7/136 | 0/8 | 6/28 | 14.0 |
| Hybride + logique juridique (temps, versions, refus) | 136 | 0.618 | 0.801 | 0.86 | 0.904 | 0.726 | 0.912 | 30/30 | 8/136 | 8/8 | 1/28 | 13.6 |
| Hybride + logique juridique + reranker | 136 | 0.684 | 0.838 | 0.89 | 0.926 | 0.77 | 0.941 | 28/30 | 1/136 | 8/8 | 2/28 | 1038.5 |

### Retrieval — jeu VIERGE v5 — PREMIÈRE passe (avant correction des qualificatifs génériques ; ranking inchangé par cette correction)

| Pipeline | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | R@5 (successeur accepté) | Refus corrects | Faux refus (questions valides) | Clarif. | Texte périmé en tête | Recherche (ms/question) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 36 | 0.5 | 0.75 | 0.75 | 0.889 | 0.627 | 0.75 | 5/6 | — | 0/3 | 2/13 | 2.7 |
| BM25 pur | 36 | 0.444 | 0.667 | 0.722 | 0.833 | 0.573 | 0.722 | 5/6 | — | 0/3 | 3/13 | 5.0 |
| Vectorielle pure (e5-small) | 36 | 0.611 | 0.722 | 0.75 | 0.861 | 0.676 | 0.778 | 6/6 | — | 0/3 | 4/13 | 35.5 |
| Hybride simple (BM25 + vecteurs, RRF) | 36 | 0.611 | 0.833 | 0.861 | 0.889 | 0.719 | 0.861 | 6/6 | — | 0/3 | 4/13 | 38.1 |
| Hybride + logique juridique (temps, versions, refus) | 36 | 0.694 | 0.833 | 0.833 | 0.889 | 0.774 | 0.861 | 6/6 | — | 1/3 | 1/13 | 37.9 |
| Hybride + logique juridique + reranker | 36 | 0.75 | 0.833 | 0.861 | 0.889 | 0.8 | 0.917 | 6/6 | — | 1/3 | 1/13 | 585.0 |

### Retrieval — v2 + v3 + v4 (100 questions ; v3 et v4 consultés pour corriger des bogues)

| Pipeline | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | R@5 (successeur accepté) | Refus corrects | Faux refus (questions valides) | Clarif. | Texte périmé en tête | Recherche (ms/question) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 100 | 0.53 | 0.72 | 0.77 | 0.86 | 0.642 | 0.82 | 15/24 | — | 0/5 | 3/15 | 2.3 |
| BM25 pur | 100 | 0.49 | 0.65 | 0.7 | 0.82 | 0.592 | 0.76 | 10/24 | — | 0/5 | 2/15 | 3.2 |
| Vectorielle pure (e5-small) | 100 | 0.55 | 0.73 | 0.76 | 0.81 | 0.636 | 0.8 | 20/24 | — | 0/5 | 4/15 | 15.2 |
| Hybride simple (BM25 + vecteurs, RRF) | 100 | 0.57 | 0.75 | 0.83 | 0.88 | 0.678 | 0.86 | 20/24 | — | 0/5 | 2/15 | 18.2 |
| Hybride + logique juridique (temps, versions, refus) | 100 | 0.59 | 0.79 | 0.87 | 0.91 | 0.709 | 0.93 | 24/24 | — | 5/5 | 0/15 | 17.3 |
| Hybride + logique juridique + reranker | 100 | 0.66 | 0.84 | 0.89 | 0.93 | 0.756 | 0.94 | 24/24 | — | 5/5 | 1/15 | 593.3 |

### Retrieval — jeu v4 (écrit après le réglage des seuils, avant la résolution de versions)

| Pipeline | n | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | R@5 (successeur accepté) | Refus corrects | Faux refus (questions valides) | Clarif. | Texte périmé en tête | Recherche (ms/question) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 18 | 0.611 | 0.778 | 0.778 | 0.833 | 0.691 | 0.778 | 2/6 | — | 0/2 | 1/7 | 1.9 |
| BM25 pur | 18 | 0.5 | 0.667 | 0.722 | 0.778 | 0.592 | 0.722 | 2/6 | — | 0/2 | 0/7 | 1.9 |
| Vectorielle pure (e5-small) | 18 | 0.444 | 0.778 | 0.833 | 0.833 | 0.597 | 0.833 | 6/6 | — | 0/2 | 2/7 | 5.7 |
| Hybride simple (BM25 + vecteurs, RRF) | 18 | 0.611 | 0.778 | 0.833 | 0.833 | 0.696 | 0.833 | 6/6 | — | 0/2 | 0/7 | 8.0 |
| Hybride + logique juridique (temps, versions, refus) | 18 | 0.611 | 0.778 | 0.833 | 0.889 | 0.706 | 0.889 | 6/6 | — | 2/2 | 0/7 | 8.0 |
| Hybride + logique juridique + reranker | 18 | 0.667 | 0.833 | 0.889 | 0.944 | 0.76 | 0.944 | 6/6 | — | 2/2 | 0/7 | 542.2 |

### Retrieval par catégorie (MRR ; n = questions avec passage attendu)

| Catégorie | n | legacy | bm25 | vector | hybrid_plain | hybrid | hybrid_rerank |
|---|---:|---:|---:|---:|---:|---:|---:|
| arabe | 13 | 0.242 | 0.0 | 0.615 | 0.615 | 0.615 | 0.654 |
| direct_definition | 6 | 0.889 | 0.889 | 1.0 | 1.0 | 0.917 | 0.889 |
| direct_delai | 6 | 0.806 | 0.833 | 1.0 | 1.0 | 1.0 | 1.0 |
| direct_interdiction | 3 | 1.0 | 1.0 | 0.75 | 0.833 | 0.697 | 0.53 |
| direct_montant | 2 | 1.0 | 1.0 | 1.0 | 1.0 | 0.583 | 0.571 |
| direct_obligation | 6 | 0.69 | 0.69 | 0.778 | 0.889 | 1.0 | 0.917 |
| direct_procedure | 4 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| etat_actuel | 8 | 0.458 | 0.228 | 0.302 | 0.293 | 0.525 | 0.812 |
| evolutif | 5 | 0.353 | 0.353 | 0.262 | 0.3 | 0.7 | 0.7 |
| fond | 40 | 0.694 | 0.694 | 0.734 | 0.756 | 0.671 | 0.696 |
| historique | 19 | 0.619 | 0.646 | 0.768 | 0.774 | 0.853 | 0.905 |
| modification | 9 | 0.62 | 0.583 | 0.241 | 0.456 | 0.707 | 0.775 |
| multi_textes | 6 | 0.211 | 0.196 | 0.208 | 0.204 | 0.158 | 0.269 |
| reference | 6 | 1.0 | 0.667 | 0.274 | 0.533 | 0.833 | 1.0 |
| relation | 2 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| temporel | 1 | 1.0 | 0.333 | 0.25 | 0.5 | 1.0 | 1.0 |

### Refus et clarifications par catégorie (corrects / total)

| Catégorie | legacy | bm25 | vector | hybrid_plain | hybrid | hybrid_rerank |
|---|---:|---:|---:|---:|---:|---:|
| ambigu | 0/8 | 0/8 | 0/8 | 0/8 | 8/8 | 8/8 |
| hors_corpus | 4/10 | 3/10 | 10/10 | 10/10 | 10/10 | 8/10 |
| hors_sujet | 12/16 | 11/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| trap_article_inexistant | 1/1 | 0/1 | 0/1 | 0/1 | 1/1 | 1/1 |
| trap_texte_inexistant | 3/3 | 1/3 | 0/3 | 0/3 | 3/3 | 3/3 |

### Bout en bout (recherche + Qwen3-4B local) — jeux v3 + v4 + v5

| Pipeline | Exactitude finale | v3 | v4 | v5 (vierge) | Recherche moy. | LLM moy. (par appel) | Total moyen / question |
|---|---:|---:|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 0.589 (66/112) | 20/41 | 17/26 | 29/45 | 3.9 ms | 35.8 s | 28.8 s |
| BM25 pur | non mesuré | | | | | | |
| Vectorielle pure (e5-small) | non mesuré | | | | | | |
| Hybride simple (BM25 + vecteurs, RRF) | non mesuré | | | | | | |
| Hybride + logique juridique (temps, versions, refus) | 0.795 (89/112) | 34/41 | 19/26 | 36/45 | 21.9 ms | 28.7 s | 20.0 s |
| Hybride + logique juridique + reranker | 0.857 (96/112) | 36/41 | 22/26 | 38/45 | 1011.1 ms | 29.9 s | 23.7 s |

### Bout en bout — notation automatique et relecture IA des échecs (PAS une relecture par un juriste humain)

| Pipeline | Auto (strict, littéral) | Après relecture IA | Récupérés (faux négatifs de notation) | Rétrogradés (faux positifs) |
|---|---:|---:|---|---|
| Recherche actuelle (BM25 + règles, avant phase 2) | 66/112 (0.589) | 75/112 (0.670) | V006, V007, V008, V010, V012, V021, V023, W005, W013, X008 | X029 |
| Hybride + logique juridique (temps, versions, refus) | 89/112 (0.795) | 92/112 (0.821) | V006, V007, V023, W005, W013, X009 | V010, V011, X029 |
| Hybride + logique juridique + reranker | 96/112 (0.857) | 100/112 (0.893) | V006, V007, V023, V039, W005, W013, X008, X009 | V010, V011, X024, X029 |

Règles de relecture :`agent_fr/eval/adjudicate.py` (preuve vérifiée mécaniquement dans les passages cités ; rétrogradation mécanique des listes incomplètes et des réponses hésitantes).

### Bout en bout par catégorie (réponses correctes / questions)

| Catégorie | legacy | hybrid | hybrid_rerank |
|---|---:|---:|---:|
| ambigu | 0/8 | 8/8 | 8/8 |
| arabe | 0/13 | 5/13 | 10/13 |
| direct_definition | 6/6 | 6/6 | 6/6 |
| direct_delai | 5/6 | 6/6 | 6/6 |
| direct_interdiction | 1/3 | 1/3 | 1/3 |
| direct_montant | 1/2 | 1/2 | 1/2 |
| direct_obligation | 4/6 | 4/6 | 4/6 |
| direct_procedure | 4/4 | 4/4 | 4/4 |
| etat_actuel | 5/8 | 7/8 | 7/8 |
| historique | 13/19 | 15/19 | 16/19 |
| hors_corpus | 10/10 | 10/10 | 10/10 |
| hors_sujet | 10/10 | 10/10 | 10/10 |
| modification | 5/9 | 8/9 | 8/9 |
| multi_textes | 0/6 | 2/6 | 3/6 |
| reference | 2/2 | 2/2 | 2/2 |
