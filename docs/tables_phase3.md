### Retrieval (questions à réponse attendue)

| Mesure | dev | test |
|---|---:|---:|
| n (questions à réponse attendue) | 64 | 42 |
| Recall@1 | 0.641 (41/64) | 0.500 (21/42) |
| Recall@3 | 0.797 (51/64) | 0.619 (26/42) |
| Recall@5 | 0.828 (53/64) | 0.714 (30/42) |
| Recall@10 | 0.859 (55/64) | 0.762 (32/42) |
| MRR | 0.723 (46/64) | 0.582 (24/42) |
| Texte@1 | 0.703 (45/64) | 0.595 (25/42) |
| Texte@5 | 0.891 (57/64) | 0.786 (33/42) |
| Article@1 | 0.621 (36/58) | 0.500 (21/42) |
| Article@5 | 0.810 (47/58) | 0.714 (30/42) |
| Exactitude temporelle@1 | 0.667 (28/42) | 0.517 (15/29) |
| Exactitude juridique@1 | 0.881 (37/42) | 0.793 (23/29) |

### Réponse finale (Qwen3-4B local)

| Mesure | dev | test |
|---|---:|---:|
| Retrieval correct (top-5) | 0.828 (53/64) | 0.714 (30/42) |
| Contexte suffisant | 0.828 (53/64) | 0.667 (28/42) |
| C1 répond (faits clés) | 0.797 (51/64) | 0.690 (29/42) |
| C2 soutenue par les sources citées | 0.844 (54/64) | 0.738 (31/42) |
| C3 bonne version | 0.766 (49/64) | 0.643 (27/42) |
| C4 citation correcte | 0.766 (49/64) | 0.619 (26/42) |
| C5 rien hors contexte | 0.922 (59/64) | 0.929 (39/42) |
| **Réponse correcte (C1–C5)** | 0.609 (39/64) | 0.524 (22/42) |
| Statut juridique correct | 0.846 (33/39) | 0.783 (18/23) |
| Hallucination (auto) | 0.125 (8/64) | 0.143 (6/42) |
| Refus à tort | 0.109 (7/64) | 0.143 (6/42) |
| Erreur temporelle critique | 0.035 (2/57) | 0.000 (0/35) |

### Refus, clarification, hors corpus

| Mesure | dev | test |
|---|---:|---:|
| Refus corrects (hors corpus + hors sujet) | 1.000 (9/9) | 0.857 (6/7) |
| Question à refuser avec réponse | 0.000 (0/9) | 0.143 (1/7) |
| Clarification demandée (questions ambiguës) | 1.000 (5/5) | 0.333 (1/3) |

### Par type de question — dev

| Type | n | Recall@5 | MRR | Temporel@1 | Réponse correcte | Hallucination | Refus / clarif. |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_direct | 16 | 0.938 (15/16) | 0.906 (14/16) | non mesuré | 0.875 (14/16) | 0.000 (0/16) | non mesuré |
| B_multi_textes | 5 | 0.000 (0/5) | 0.029 (0/5) | 0.500 (2/4) | 0.200 (1/5) | 0.200 (1/5) | non mesuré |
| C_temporelle | 18 | 0.944 (17/18) | 0.852 (15/18) | 0.778 (14/18) | 0.722 (13/18) | 0.111 (2/18) | non mesuré |
| D_modification | 7 | 1.000 (7/7) | 0.702 (5/7) | 0.571 (4/7) | 0.714 (5/7) | 0.000 (0/7) | non mesuré |
| E_abrogation | 6 | 1.000 (6/6) | 1.000 (6/6) | 1.000 (6/6) | 0.833 (5/6) | 0.000 (0/6) | non mesuré |
| F_comparaison | 4 | 0.500 (2/4) | 0.250 (1/4) | 0.500 (2/4) | 0.000 (0/4) | 0.750 (3/4) | non mesuré |
| G_ambigue | 5 | non mesuré | non mesuré | non mesuré | 1.000 (5/5) | non mesuré | 1.000 (5/5) |
| H_hors_corpus | 6 | non mesuré | non mesuré | non mesuré | 1.000 (6/6) | non mesuré | 1.000 (6/6) |
| I_hors_sujet | 3 | non mesuré | non mesuré | non mesuré | 1.000 (3/3) | non mesuré | 1.000 (3/3) |
| J_fr_ar | 8 | 0.750 (6/8) | 0.544 (4/8) | 0.000 (0/3) | 0.125 (1/8) | 0.250 (2/8) | non mesuré |

**Sous-benchmark temporalité — dev** (n = 41) : Recall@1 0.585 (24/41) ; exactitude temporelle@1 0.683 (28/41) ; exactitude juridique@1 0.878 (36/41) ; réponse correcte 0.561 (23/41) ; statut correct 0.861 (31/36) ; erreurs temporelles critiques 0.056 (2/36)

### Par type de question — test

| Type | n | Recall@5 | MRR | Temporel@1 | Réponse correcte | Hallucination | Refus / clarif. |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_direct | 10 | 0.900 (9/10) | 0.850 (8/10) | non mesuré | 0.800 (8/10) | 0.000 (0/10) | non mesuré |
| B_multi_textes | 3 | 0.667 (2/3) | 0.178 (1/3) | 0.667 (2/3) | 0.333 (1/3) | 0.333 (1/3) | non mesuré |
| C_temporelle | 11 | 0.636 (7/11) | 0.591 (7/11) | 0.545 (6/11) | 0.455 (5/11) | 0.364 (4/11) | non mesuré |
| D_modification | 5 | 0.400 (2/5) | 0.265 (1/5) | 0.200 (1/5) | 0.200 (1/5) | 0.000 (0/5) | non mesuré |
| E_abrogation | 4 | 1.000 (4/4) | 1.000 (4/4) | 1.000 (4/4) | 0.750 (3/4) | 0.000 (0/4) | non mesuré |
| F_comparaison | 3 | 0.667 (2/3) | 0.283 (1/3) | 0.333 (1/3) | 0.667 (2/3) | 0.000 (0/3) | non mesuré |
| G_ambigue | 3 | non mesuré | non mesuré | non mesuré | 0.333 (1/3) | non mesuré | 0.333 (1/3) |
| H_hors_corpus | 4 | non mesuré | non mesuré | non mesuré | 0.750 (3/4) | non mesuré | 0.750 (3/4) |
| I_hors_sujet | 3 | non mesuré | non mesuré | non mesuré | 1.000 (3/3) | non mesuré | 1.000 (3/3) |
| J_fr_ar | 6 | 0.667 (4/6) | 0.458 (3/6) | 0.333 (1/3) | 0.333 (2/6) | 0.167 (1/6) | non mesuré |

**Sous-benchmark temporalité — test** (n = 29) : Recall@1 0.414 (12/29) ; exactitude temporelle@1 0.517 (15/29) ; exactitude juridique@1 0.793 (23/29) ; réponse correcte 0.448 (13/29) ; statut correct 0.783 (18/23) ; erreurs temporelles critiques 0.000 (0/23)
