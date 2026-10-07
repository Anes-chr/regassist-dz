## Comparaison des moteurs de recherche (retrieval seul, sans LLM) sur le benchmark humain

Même corpus final, mêmes questions ; `hybrid_rerank` est le moteur évalué dans la suite du rapport. « Refus corrects » = hors corpus + hors sujet ; « clarif. » = questions ambiguës.

### DEV

| Moteur | n | R@1 | R@3 | R@5 | R@10 | MRR | Temporel@1 | Juridique@1 | Refus corrects | Clarif. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 64 | 0.453 | 0.594 | 0.656 | 0.734 | 0.547 | 0.524 | 0.714 | 3/9 | 0/5 |
| bm25 | 64 | 0.406 | 0.578 | 0.656 | 0.719 | 0.510 | 0.476 | 0.714 | 2/9 | 0/5 |
| vector | 64 | 0.359 | 0.562 | 0.688 | 0.766 | 0.481 | 0.310 | 0.667 | 9/9 | 0/5 |
| hybrid_plain | 64 | 0.422 | 0.641 | 0.734 | 0.812 | 0.544 | 0.405 | 0.667 | 9/9 | 0/5 |
| hybrid | 64 | 0.531 | 0.734 | 0.812 | 0.859 | 0.646 | 0.524 | 0.881 | 9/9 | 5/5 |
| hybrid_rerank | 64 | 0.641 | 0.797 | 0.828 | 0.859 | 0.723 | 0.667 | 0.881 | 8/9 | 5/5 |

### TEST

| Moteur | n | R@1 | R@3 | R@5 | R@10 | MRR | Temporel@1 | Juridique@1 | Refus corrects | Clarif. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 42 | 0.357 | 0.405 | 0.500 | 0.619 | 0.422 | 0.345 | 0.759 | 2/7 | 0/3 |
| bm25 | 42 | 0.357 | 0.381 | 0.500 | 0.619 | 0.417 | 0.345 | 0.690 | 2/7 | 0/3 |
| vector | 42 | 0.452 | 0.524 | 0.595 | 0.738 | 0.523 | 0.379 | 0.793 | 7/7 | 0/3 |
| hybrid_plain | 42 | 0.429 | 0.500 | 0.595 | 0.762 | 0.511 | 0.310 | 0.828 | 7/7 | 0/3 |
| hybrid | 42 | 0.405 | 0.571 | 0.690 | 0.762 | 0.517 | 0.276 | 0.862 | 7/7 | 1/3 |
| hybrid_rerank | 42 | 0.500 | 0.619 | 0.714 | 0.762 | 0.582 | 0.517 | 0.793 | 6/7 | 1/3 |

### Sensibilité : classement calculé sur la liste de production (k = 6) au lieu de k = 10 (`hybrid_rerank`)

| Split | R@1 (k=6 / k=10) | R@3 | R@5 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| DEV | 0.641 / 0.641 | 0.797 / 0.797 | 0.828 / 0.828 | 0.828 / 0.859 | 0.719 / 0.723 |
| TEST | 0.500 / 0.500 | 0.619 / 0.619 | 0.714 / 0.714 | 0.738 / 0.762 | 0.581 / 0.582 |

(R@10 n'est pas défini sur une liste de 6 passages.)

## Incertitude statistique (intervalle de Wilson à 95 %)

Les effectifs sont petits (DEV 64 et TEST 42 questions à réponse attendue) : une différence de quelques points entre DEV et TEST n'est pas significative.

| Mesure | DEV | TEST |
|---|---|---|
| Recall@5 | 53/64 = 0.828 [0.718 ; 0.901] | 30/42 = 0.714 [0.564 ; 0.828] |
| Réponse correcte (C1–C5) | 39/64 = 0.609 [0.487 ; 0.719] | 22/42 = 0.524 [0.377 ; 0.666] |
| Hallucination (auto) | 8/64 = 0.125 [0.065 ; 0.228] | 6/42 = 0.143 [0.067 ; 0.278] |
| Refus à tort | 7/64 = 0.109 [0.054 ; 0.209] | 6/42 = 0.143 [0.067 ; 0.278] |
| Erreur temporelle critique | 2/57 = 0.035 [0.010 ; 0.119] | 0/35 = 0.000 [0.000 ; 0.099] |
| Refus corrects (hors corpus + hors sujet) | 9/9 = 1.000 [0.701 ; 1.000] | 6/7 = 0.857 [0.487 ; 0.974] |
| Clarification (ambiguës) | 5/5 = 1.000 [0.566 ; 1.000] | 1/3 = 0.333 [0.061 ; 0.792] |

## Relecture IA (non humaine) des réponses rejetées par la notation automatique

Aucune règle de notation n'est modifiée ; ces tableaux documentent les causes d'échec et les divergences probables avec une évaluation humaine. Seules les réponses rejetées sont relues (asymétrie : borne haute de l'exactitude).

| Split | Réponses correctes (auto) | Rejetées relues | correcte | correcte_avec_defaut | a_arbitrer | partielle | incorrecte | Exactitude auto | Estimation IA (auto + correcte + avec défaut) | Estimation IA haute (+ à arbitrer) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV | 39/64 | 25 | 7 | 1 | 1 | 3 | 13 | 0.609 | 47/64 = 0.734 | 48/64 = 0.750 |
| TEST | 22/42 | 20 | 3 | 2 | 2 | 1 | 12 | 0.524 | 27/42 = 0.643 | 29/42 = 0.690 |

### Causes des échecs relus

| Cause | DEV | TEST | Définition |
|---|---:|---:|---|
| RETR_DOC | 6 | 4 | le bon texte n'est pas dans les 5 premiers passages |
| SCORER | 4 | 3 | notation automatique trop stricte |
| LLM_REFUS | 3 | 2 | le bon passage est dans le contexte mais le LLM répond qu'il ne trouve rien |
| OCR_AR | 4 | 1 | texte arabe OCR altéré (chiffres, mots, passage tronqué) à l'origine de l'erreur |
| HINT_LEAK | 2 | 2 | date de référence de la consigne interne reprise comme si elle venait des sources |
| GOLD_ARB | 1 | 2 | source attendue à arbitrer par le juriste |
| RETR_ART | 1 | 2 | bon texte, mauvais article / article de la valeur absent du contexte |
| LLM_CHAIN | 1 | 2 | le LLM nomme le mauvais texte dans une chaîne de modifications/abrogations, ou synthèse multi-textes incomplète |
| DERIVED_NUMBER | 3 | 0 | nombre calculé par le modèle (différence) ou chiffres écrits en lettres puis en chiffres, absent tel quel du contexte |
| AMBIG_MISS | 0 | 2 | question ambiguë non détectée |
| RETR_REFUS | 0 | 1 | refus décidé par le moteur de recherche (aucun passage pertinent) alors que la réponse existe |
| OOS_ANSWERED | 0 | 1 | question hors corpus traitée comme valide |
| CORPUS_ID | 0 | 1 | défaut d'identification du texte dans le corpus (jumeau FR/AR non rattaché, date erronée) |

## Re-mesure des jeux historiques (gold_v2 … v5, 136 questions avec retrieval) sur le corpus final

Retrieval seul ; identifiants remappés par empreinte de fichier ; résultats **non strictement comparables** à ceux de la phase 2 (corpus différent) et jamais mélangés au benchmark humain.

| Moteur | Mesure | Phase 2 (corpus 2026-10-06) | Phase 3 (corpus final) |
|---|---|---:|---:|
| hybrid_rerank | R@1 | 0.684 | 0.654 |
| hybrid_rerank | R@3 | 0.838 | 0.816 |
| hybrid_rerank | R@5 | 0.89 | 0.853 |
| hybrid_rerank | R@10 | 0.926 | 0.912 |
| hybrid_rerank | MRR | 0.77 | 0.742 |
| hybrid_rerank | faux_refus | 1/136 | 1/136 |
| hybrid_rerank | refus_ok | 28/30 | 28/30 |
| hybrid_rerank | clarif_ok | 8/8 | 8/8 |
| hybrid_rerank | perime_en_tete | 2/28 | 3/28 |
| legacy | R@1 | 0.522 | 0.522 |
| legacy | R@3 | 0.728 | 0.728 |
| legacy | R@5 | 0.765 | 0.765 |
| legacy | R@10 | 0.868 | 0.868 |
| legacy | MRR | 0.638 | 0.637 |
| legacy | faux_refus | 11/136 | 11/136 |
| legacy | refus_ok | 20/30 | 20/30 |
| legacy | clarif_ok | 0/8 | 0/8 |
| legacy | perime_en_tete | 5/28 | 5/28 |


## Mesures d'ablation et de simulation (hors système évalué, retrieval seul)

Ces mesures documentent l'effet de la règle de séries (nouvelle en phase 3) et d'un défaut de relations du corpus (voir §1 du rapport). Elles ne modifient ni le moteur ni le corpus évalués.

| Mesure | Système évalué | Facteur de série désactivé | Relations repointées vers le document FR (simulation) |
|---|---:|---:|---:|
| Jeux historiques R@1 (136 questions) | 0.654 | 0.669 | 0.662 |
| Jeux historiques R@3 (136 questions) | 0.816 | 0.831 | 0.824 |
| Jeux historiques R@5 (136 questions) | 0.853 | 0.875 | 0.86 |
| Jeux historiques MRR (136 questions) | 0.742 | 0.756 | 0.749 |
| Benchmark humain DEV R@1 (64 questions) | 0.641 | 0.641 | 0.641 |
| Benchmark humain DEV R@3 (64 questions) | 0.797 | 0.766 | 0.797 |
| Benchmark humain DEV R@5 (64 questions) | 0.828 | 0.812 | 0.828 |
| Benchmark humain DEV MRR (64 questions) | 0.723 | 0.713 | 0.723 |
| Benchmark humain DEV juridique@1 (64 questions) | 0.881 | 0.833 | 0.881 |
## Performances (machine : i7-13700, 24 threads, 15,6 Go de RAM, sans GPU, llama-server chargé)

| Mesure | Phase 2 | Phase 3 (corpus final) |
|---|---:|---:|
| RSS agent après chargement (Mo) | 1667.4 | 1671.4 |
| RSS llama-server (Mo) | 3007.3 | 3018.3 |
| retrieval hybrid_rerank, total moy. (ms) | 893.2 | 502.6 |
| retrieval hybrid_rerank, total p95 (ms) | 1391.0 | 720.6 |
|   dont embedding question moy. (ms) | 23.4 | 7.1 |
|   dont recherche BM25 + vecteurs moy. (ms) | 4.3 | 4.8 |
|   dont reranking moy. (ms) | 864.3 | 488.9 |
| retrieval hybrid (sans reranker), total moy. (ms) | 9.0 | 11.8 |
| premier appel hybrid_rerank (s) | 1.22 | 1.21 |

| Bout en bout (Qwen3-4B local, mesuré pendant les runs DEV/TEST) | n appels LLM | LLM moy. / médiane / p95 / max (s) | Total par question moy. / médiane / p95 (s) |
|---|---:|---:|---:|
| DEV (78 questions) | 65 | 33.5 / 30.1 / 53.2 / 72.4 | 28.5 / 28.4 / 52.6 |
| TEST (52 questions) | 44 | 39.3 / 34.5 / 76.2 / 96.5 | 33.9 / 30.5 / 74.5 |
