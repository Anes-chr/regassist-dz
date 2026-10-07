## A. Corpus : avant (phase 3 final) / après (phase 4)

| Mesure | Phase 3 | Phase 4 |
|---|---:|---:|
| Documents | 1085 | 1085 |
| Chunks (FR + AR + indéterminée) | 11112 | 11320 |
| Identifiants de chunks en double (occurrences en trop / identifiants / chunks concernés) | 107 / 76 / 183 | 0 / 0 / 0 |
| Articles arabes détectés | 2405 | 2634 |
| Documents arabes sans aucun article détecté | 35 | 27 |
| Documents arabes / indéterminés sans jumeau de même work_id | 37 | 28 |
| Chunks arabes marqués OCR_UNCERTAIN (valeur numérique non corroborée) | non mesuré | 80 (dans 62 documents) |
| Textes distincts (work_id) | 679 | 670 |

Chunks dont le texte est identique entre les deux versions : 10986 / 11320 (nouveaux textes : 334 ; textes disparus : 126).

## B. Les 12 jumeaux arabes non rattachés de la phase 3

| Document FR | Document AR (phase 3) | N° | Date FR | Date AR avant → après | Relation attendue | Relation avant | Relation après |
|---|---|---|---|---|---|---|---|
| REG-02-01-20020217.fr | REG-02-01-20020220.ar | 2002-01 | 2002-02-17 | 2002-02-20 → 2002-02-20 | même work_id (même type + même numéro + même date) | work_id distincts : REG-02-01-20020217 / REG-02-01-20020220 | NON rattachés : REG-02-01-20020217 / REG-02-01-20020220 — conflit de dates documenté, arbitrage humain (twin_overrides.json) |
| REG-06-01-20060907.fr | REG-06-01-20060514.ar | 2006-01 | 2006-09-07 | 2006-05-14 → 2006-05-14 | même work_id (même type + même numéro + même date) | work_id distincts : REG-06-01-20060907 / REG-06-01-20060514 | NON rattachés : REG-06-01-20060907 / REG-06-01-20060514 — conflit de dates documenté, arbitrage humain (twin_overrides.json) |
| REG-90-01-19900704.fr | REG-90-01-19900604.ar | 90-01 | 1990-07-04 | 1990-06-04 → 1990-06-04 | même work_id (même type + même numéro + même date) | work_id distincts : REG-90-01-19900704 / REG-90-01-19900604 | NON rattachés : REG-90-01-19900704 / REG-90-01-19900604 — conflit de dates documenté, arbitrage humain (twin_overrides.json) |
| REG-06-02-20060924.fr | REG-06-02.ar | 2006-02 | 2006-09-24 | None → 2006-09-24 | même work_id (même type + même numéro + même date) | work_id distincts : REG-06-02-20060924 / REG-06-02 | rattachés : REG-06-02 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| REG-91-02-19910220.fr | REG-91-02.ar | 91-02 | 1991-02-20 | None → 1991-02-20 | même work_id (même type + même numéro + même date) | work_id distincts : REG-91-02-19910220 / REG-91-02 | rattachés : REG-91-02 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| REG-04-04-20040719.fr | REG-04-04.ar | 2004-04 | 2004-07-19 | None → 2004-07-19 | même work_id (même type + même numéro + même date) | work_id distincts : REG-04-04-20040719 / REG-04-04 | rattachés : REG-04-04 (R-TWIN-JOURMOIS) |
| REG-08-04-20081223.fr | REG-08-04-20051223.ar | 2008-04 | 2008-12-23 | 2005-12-23 → 2008-12-23 | même work_id (même type + même numéro + même date) | work_id distincts : REG-08-04-20081223 / REG-08-04-20051223 | rattachés : REG-08-04 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| REG-91-09-19910814.fr | REG-91-09.ar | 91-09 | 1991-08-14 | None → 1991-08-14 | même work_id (même type + même numéro + même date) | work_id distincts : REG-91-09-19910814 / REG-91-09 | rattachés : REG-91-09 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| REG-92-10-19921117.fr | REG-92-10.ar | 92-10 | 1992-11-17 | None → 1992-11-17 | même work_id (même type + même numéro + même date) | work_id distincts : REG-92-10-19921117 / REG-92-10 | rattachés : REG-92-10 (R-TWIN-JOURMOIS) |
| INS-08-21-20210701.fr | INS-08-21.ar | 08-2021 | 2021-07-01 | None → 2021-07-01 | même work_id (même type + même numéro + même date) | work_id distincts : INS-08-21-20210701 / INS-08-21 | rattachés : INS-08-21 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| LD-02-24-20241128.fr | LD-02-24.ar | 02-2024 | 2024-11-28 | None → 2024-11-28 | même work_id (même type + même numéro + même date) | work_id distincts : LD-02-24-20241128 / LD-02-24 | rattachés : LD-02-24 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |
| REG-25-03-20250414.fr | REG-25-03.ar | 25-03 | 2025-04-14 | None → 2025-04-14 | même work_id (même type + même numéro + même date) | work_id distincts : REG-25-03-20250414 / REG-25-03 | rattachés : REG-25-03 (R-TWIN-DATE (date lue dans le libellé arabe corrigé)) |

## C. Les 76 identifiants de chunks en double de la phase 3

76 identifiants, 183 chunks ; **chunks de texte identique : 0** (aucun doublon réel) ; tailles de groupe : {2: 55, 4: 10, 3: 11}.

| Cause | Identifiants |
|---|---:|
| articles dont la numérotation recommence dans le même texte (additif, partie 2…) | 35 |
| annexes dont le numéro a été lu « N » ou « رقم » (défaut d'analyse de l'en-tête) | 25 |
| annexes de même numéro dans un même texte (annexes I, II… répétées par partie) | 16 |

Cause commune : la détection d'un doublon ne comparait qu'aux 3 derniers chunks (`chunk.py`). Correctif : identifiant unique par document (`::u<indice de l'unité>`), stable et déterministe ; 0 doublon après reconstruction.

## D. Liens morts : 38 entrées = 19 URLs uniques

Résolution : {'MOVED_OFFICIAL': 19} ; confiance : {'forte (nom de fichier + type + numéro)': 15, "forte (nom de fichier + intitulé tronqué contenu dans l'intitulé du document)": 1, 'moyenne+ (nom de fichier identique + même page de liste du site ; intitulé du lien tronqué)': 3}. Vérification en ligne le 2026-10-07T08:14:48+00:00 : ancien chemin → HTTP [404], URL officielle de remplacement → HTTP [200].

| Ancien lien (404) | Document du corpus | URL officielle actuelle | Confiance |
|---|---|---|---|
| …/pdf/instructions1990/instruction0690.pdf | INS-06-90.fr | …/stoodroa/2021/03/instruction0690.pdf | forte |
| …/pdf/instructions1995/instruction7895.pdf | INS-78-95.fr | …/stoodroa/2021/03/instruction7895.pdf | forte |
| …/pdf/instructions1995/instruction7995.pdf | INS-79-95.fr | …/stoodroa/2021/02/instruction7995.pdf | forte |
| …/pdf/instructions2002/instruction042002.pdf | INS-04-02.fr | …/stoodroa/2021/03/instruction042002.pdf | forte |
| …/pdf/instructions2004/instruction012004.pdf | INS-01-04.fr | …/stoodroa/2021/03/instruction012004.pdf | forte |
| …/pdf/instructions2011/instruction042011.pdf | INS-04-11.fr | …/stoodroa/2021/02/instruction042011.pdf | forte |
| …/pdf/instructions2011/instruction062011.pdf | INS-06-11.fr | …/stoodroa/2021/02/instruction062011.pdf | forte |
| …/pdf/instructions2017/instruction022017.pdf | INS-02-17.fr | …/stoodroa/2021/02/instruction022017.pdf | forte |
| …/pdf/instructions2017/instruction062017.pdf | INS-06-17.fr | …/stoodroa/2021/02/instruction062017.pdf | forte |
| …/pdf/instructions2020/instruction112020.pdf | INS-11-20.fr | …/stoodroa/2021/02/instruction112020.pdf | forte |
| …/pdf/instructions2021/instruction022021.pdf | INS-02-21.fr | …/stoodroa/2021/02/instruction022021.pdf | forte |
| …/pdf/nb1998/note1198.pdf | NOT-11-98.fr | …/stoodroa/2021/05/note1198.pdf | moyenne+ |
| …/pdf/nb1998/notedgrfe_081298.pdf | NOT-NA-310c2beb.fr | …/stoodroa/2021/05/notedgrfe_081298.pdf | moyenne+ |
| …/pdf/nb1998/noteorientation0398.pdf | NOT-03-19980621.fr | …/stoodroa/2021/05/noteorientation0398.pdf | moyenne+ |
| …/pdf/reglements1994/reglement9417.pdf | REG-94-17.fr | …/stoodroa/2023/01/reglement9417.pdf | forte |
| …/pdf/reglements1995/reglement9508.pdf | REG-95-08.fr | …/stoodroa/2021/03/reglement9508.pdf | forte |
| …/pdf/reglements2009/reglement200901.pdf | REG-09-01.fr | …/stoodroa/2023/01/reglement200901.pdf | forte |
| …/pdf/reglements2017/reglement201701.pdf | REG-17-01.fr | …/stoodroa/2021/02/reglement201701.pdf | forte |
| …/pdf/reglements2020/reglement202004.pdf | REG-20-04.fr | …/stoodroa/2021/02/reglement202004.pdf | forte |

## E. Benchmark OCR arabe : OCR actuel / tessdata_best

Jeu A = pages à couche texte native rendues puis passées à l'OCR (vérité exacte ; 7 documents, 14 pages ; 3 documents à couche texte partiellement corrompue exclus) ; jeu B = scans problématiques, vérité des valeurs = texte du jumeau français (19 documents).

| Mesure | OCR actuel | tessdata_best | Écart |
|---|---:|---:|---:|
| Exactitude caractères (jeu A) | 0.821 | 0.847 | +0.027 |
| Jeu A — Chiffres (rappel) | 0.960 | 0.954 | -0.006 |
| Jeu A — Montants (rappel) | 1.000 | 1.000 | +0.000 |
| Jeu A — Dates (rappel) | 0.934 | 0.934 | +0.000 |
| Jeu A — Numéros d'articles (rappel) | 0.914 | 0.886 | -0.028 |
| Jeu A — Numéros de textes (rappel) | 0.976 | 0.976 | +0.000 |
| Jeu A — Noms propres (rappel) | 0.636 | 0.727 | +0.091 |
| Jeu A — Termes juridiques (rappel) | 0.986 | 0.986 | +0.000 |
| Jeu B — Chiffres (rappel agrégé) | 0.337 | 0.428 | +0.091 |
| Jeu B — Pourcentages (rappel agrégé) | 0.071 | 0.107 | +0.036 |
| Jeu B — Montants (rappel agrégé) | 0.043 | 0.130 | +0.087 |
| Jeu B — Dates (rappel agrégé) | 0.398 | 0.407 | +0.009 |
| Jeu B — Numéros d'articles (rappel agrégé) | 0.585 | 0.578 | -0.007 |
| Jeu B — Numéros de textes (rappel agrégé) | 0.688 | 0.688 | +0.000 |
| Jeu B hors REG-25-07 — Chiffres | 0.581 | 0.617 | +0.036 |
| Jeu B hors REG-25-07 — Pourcentages | 0.071 | 0.107 | +0.036 |
| Jeu B hors REG-25-07 — Montants | 0.062 | 0.188 | +0.126 |
| Jeu B hors REG-25-07 — Dates | 0.330 | 0.350 | +0.020 |
| Jeu B — chiffres (moyenne par document) | 0.738 | 0.756 | +0.018 |
| Jeu B — pourcentages (moyenne par document) | 0.109 | 0.118 | +0.009 |
| Jeu B — montants (moyenne par document) | 0.303 | 0.364 | +0.061 |
| Jeu B — dates (moyenne par document) | 0.624 | 0.636 | +0.012 |
| Jeu B — articles (moyenne par document) | 0.662 | 0.640 | -0.022 |
| Jeu B — numeros_de_textes (moyenne par document) | 0.847 | 0.843 | -0.004 |
| Jeu B — nombres parasites (absents du jumeau FR), part | 0.089 | 0.074 | -0.015 |
| Jeu B hors REG-25-07 — nombres parasites | 0.139 | 0.132 | -0.007 |
| Alertes OCR_UNCERTAIN, jeu B (unités signalées / unités) | 13 / 84 | 15 / 88 | |
| Secondes par page (moyenne) | 1.51 | 2.18 | +0.67 |

Valeurs critiques lues sur les documents du benchmark juridique (OCR actuel → tessdata_best) :

| Valeur attendue (jumeau français) | OCR actuel | tessdata_best |
|---|---|---|
| INS-08-25 art. 2 : « 2,75 % » | `902.75` | `002.75` |
| INS-02-26 art. 2 : « 2,50 % » | `2,50 ١ %o‏` | `(non retrouvée)` |
| INS-01-26 art. 2 : « 1 % » | `د 1 %` | `ب 1 %` |
| REG-97-04 art. 9 : « 600.000 » | `600.000` | `600.000` |

### Détecteur OCR_UNCERTAIN (alertes critiques par article arabe comparé au français)

| Type de texte arabe | Articles comparés | Alertes | Taux |
|---|---:|---:|---:|
| couche texte native (aucune erreur d'OCR possible : plancher de faux positifs) | 155 | 0 | 0.000 |
| mixte | 144 | 0 | 0.000 |
| OCR | 2043 | 67 | 0.033 |

Raisons (OCR) : {'R-OCR-MANQUANT': 60, 'R-OCR-TAUX': 1, 'R-OCR-ABSENT-JUMEAU': 33, 'R-OCR-SYMBOLE': 4} ; dont cause « symbole % lu comme des chiffres » identifiée : 15.

## F. Régression : phase 2 / phase 3 / phase 4

### Jeux historiques (gold v2–v5, 136 questions, retrieval seul, `hybrid_rerank`)

| Mesure | Phase 2 (corpus 2026-10-06) | Phase 3 (corpus final) | Phase 4 |
|---|---:|---:|---:|
| R@1 | 0.684 | 0.654 | 0.669 |
| R@3 | 0.838 | 0.816 | 0.831 |
| R@5 | 0.89 | 0.853 | 0.868 |
| R@10 | 0.926 | 0.912 | 0.926 |
| MRR | 0.77 | 0.742 | 0.757 |
| faux_refus | 1/136 | 1/136 | 1/136 |
| refus_ok | 28/30 | 28/30 | 28/30 |
| clarif_ok | 8/8 | 8/8 | 8/8 |
| perime_en_tete | 2/28 | 3/28 | 3/28 |

| Question suivie | Phase 2 | Phase 3 | Phase 4 | Explication |
|---|---:|---:|---:|---|
| G038 Combien d'euros un résident peut-il emporter à l'étranger par an ? | 1 | None | 1 | relation FR → jumeau arabe corrigée |
| V041 ما هي المدة الممنوحة للمؤسسات للامتثال لأحكام النظام رقم 25-07؟ | 2 | None | 1 | articles arabes de REG-25-07 détectés (en-tête « المادة8. » collé) |
| W007 Quel est le taux actuel des réserves obligatoires ? | 1 | 2 | 2 | inchangé |
| X019 Quel était le taux de la prime due au fonds de garantie des dépôts ban | 1 | 8 | 8 | règle de séries (« en 2003 » = exercice 2003) : non modifiée |
| X026 Jusqu'à quelle date les banques devaient-elles verser la prime au fond | 1 | 7 | 7 | règle de séries : non modifiée |
| X028 Quelles instructions ont fixé le taux de la prime due au fonds de gara | 4 | 7 | 7 | règle de séries : non modifiée |

Questions arabes des jeux historiques (13) : Recall@5 phase 2 / 3 / 4 = 10 / 9 / 10.

### Benchmark humain DEV (64 questions à réponse attendue + 14 refus / clarifications)

| Mesure | Phase 3 (DEV) | Phase 4 (DEV) |
|---|---:|---:|
| Recall@1 | 0.641 (41/64) | 0.641 (41/64) |
| Recall@3 | 0.797 (51/64) | 0.797 (51/64) |
| Recall@5 | 0.828 (53/64) | 0.828 (53/64) |
| Recall@10 | 0.859 (55/64) | 0.859 (55/64) |
| MRR | 0.723 (46/64) | 0.723 (46/64) |
| Exactitude temporelle@1 | 0.667 (28/42) | 0.667 (28/42) |
| Exactitude juridique@1 | 0.881 (37/42) | 0.881 (37/42) |
| Contexte suffisant | 0.828 (53/64) | 0.828 (53/64) |
| C1 répond | 0.797 (51/64) | 0.781 (50/64) |
| C2 soutenue | 0.844 (54/64) | 0.828 (53/64) |
| C3 bonne version | 0.766 (49/64) | 0.750 (48/64) |
| C4 citation | 0.766 (49/64) | 0.781 (50/64) |
| C5 rien hors contexte | 0.922 (59/64) | 0.922 (59/64) |
| **Réponse correcte** | 0.609 (39/64) | 0.625 (40/64) |
| Statut correct | 0.846 (33/39) | 0.895 (34/38) |
| Hallucination (auto) | 0.125 (8/64) | 0.141 (9/64) |
| Refus à tort | 0.109 (7/64) | 0.109 (7/64) |
| Erreur temporelle critique (règle automatique) | 0.035 (2/57) | 0.018 (1/57) |
| Refus corrects | 1.000 (9/9) | 1.000 (9/9) |
| Clarifications | 1.000 (5/5) | 1.000 (5/5) |
