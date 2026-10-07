# Phase 3 — Finalisation du corpus et validation juridique

Objectif : figer le corpus, rendre les relations juridiques explicites, mesurer l'agent sur un benchmark **indépendant des réglages** (split DEV / TEST), et décider GO / CONDITIONAL GO / NO-GO.
Tout reste local : corpus, embeddings, reranker et Qwen3-4B tournent sur la machine ; aucune donnée juridique n'est envoyée à un service distant (§10).
Toutes les valeurs ci-dessous sont **mesurées** (fichiers sous `agent_fr/eval/results/`, tableaux régénérables par `python -m agent_fr.eval.human.make_tables3` et `make_tables3_extra`).
Une cellule « non mesuré » signifie qu'aucune mesure n'existe : jamais d'estimation.

> **Avertissement permanent.** Le benchmark de la phase 3 (130 questions) a été **rédigé et vérifié mécaniquement par une IA (Claude), pas par un juriste humain** : `validation_humaine.statut = en_attente`
> pour les 130 questions. Les 60 réponses à évaluer par un humain n'ont pas été évaluées. **Une relecture IA n'est pas une validation juridique** : tout ce que ce rapport appelle « relecture IA » est
> explicitement non humain. La décision du §12 est donc **provisoire** tant qu'un juriste n'a pas validé le benchmark et évalué les réponses (mode d'emploi : [HUMAN_REVIEW.md](HUMAN_REVIEW.md)).
> Statut des textes : jamais affirmé au-delà de ce que prouve le corpus (« UNKNOWN » sinon).

## 1. État du corpus (instantané figé `D:\llm\snapshots\corpus_phase3_final`)

**Collecte.** Le crawl a été relancé puis laissé terminer (il s'était bloqué pendant des heures : une session HTTP « keep-alive » provoquait des erreurs 500 côté serveur ; correctif : recyclage de session,
`boa_pipeline/client.py`). Résultat (`corpus/reports/coverage_report.json`, `extraction_report.json`) :

| Mesure | Valeur |
|---|---:|
| Pages explorées (sitemaps + liens internes) | 2 942 |
| Liens de documents trouvés / documents uniques | 5 258 / 2 824 |
| Documents dans le périmètre (textes réglementaires) / hors périmètre | 1 188 / 1 636 |
| **Documents dans le corpus final** | **1 085** (FR 757, AR 327, indéterminée 1) |
| Textes distincts (`work_id`, jumeaux FR/AR réunis) | 642 FR + 323 AR + 1 |
| Nouveaux documents apportés par la dernière passe / inchangés / modifiés | 13 / 1 156 / 0 |
| Documents en échec (liens morts 404 : 19 ; non téléchargés : 19) | 38 (liste : `failed_documents.json`) |
| Doublons : fichiers identiques / texte identique / même texte même langue | 83 / 3 / 119 (conservés comme copies `~N`, jamais départagés) |
| PDF textuels / mixtes / OCR | 778 / 23 / 307 |
| Articles extraits / chunks | 8 161 / 11 112 (FR 7 789, AR 3 317, indéterminée 6) |
| Textes sans date | 27 (FR 9, AR 18) |

Les 38 liens en échec sont des liens morts du site (aucun contournement tenté) : le corpus reste « ce que le site expose », pas une garantie d'exhaustivité (`coverage_report.json`, champ `avertissement`).

**Défauts corrigés dans la chaîne (puis vérifiés).**

| Défaut | Avant | Après | Correction |
|---|---:|---:|---|
| Couche texte PDF corrompue (caractères de contrôle, inversion lam-alef) → chunks illisibles | 106 chunks (19 documents) | 4 chunks (3 documents) | détection (`extract.py`) puis repli OCR Tesseract ara+fra à 400 dpi |
| Dates erronées (date d'un texte cité prise pour la date du document) | 43 documents suspects | 4 | dates ancrées sur le numéro du document lui-même (FR et AR) ; `work_id` refaits |
| Textes arabes sans jumeau français rattaché | non mesuré | 37 documents arabes sans jumeau de même `work_id` (dont 12 ont un texte FR de même numéro mais de date différente ou absente) | **non corrigé** (voir ci-dessous) |

**Qualité OCR arabe** (`ocr_audit_*.json`, script `ocr_audit.py` ; « rappel des nombres » = part des nombres du jumeau français retrouvés dans le texte arabe) :

| Mesure | Avant | Après |
|---|---:|---:|
| Documents arabes / chunks audités | 318 / 3 029 | 327 / 3 374 |
| Chunks illisibles | 106 | 4 |
| Caractères aberrants (moyenne) | 0,026 | 0,002 |
| Rappel des nombres (moyenne) | 0,811 | 0,852 |
| Rappel des années (moyenne) | 0,838 | 0,901 |
| Numéros d'article non numériques | 55 / 2 059 | 70 / 2 512 |
| Documents dont le rappel des nombres < 50 % | 16 | 7 |

Un essai de variantes Tesseract (300 / 400 / 500 dpi, binarisation, ara seul, psm 6 ; `ocr_pilot.json`, 12 documents) n'améliore pas nettement le rappel (0,676 pour la configuration courante ; meilleure variante 0,706 à 300 dpi,
sans amélioration des chiffres). **Le goulet est le modèle OCR, pas ses réglages** : le seul levier restant est le modèle `tessdata_best` pour l'arabe, qui exige un téléchargement (≈ 14 Mo, `github.com/tesseract-ocr/tessdata_best`) que
je n'ai pas fait sans autorisation explicite (§13).

**Modèle de statut juridique** (`agent_fr/legal_status.py`, fichier `legal_status.json` à côté des documents). Le statut de chaque texte (et de chaque article amendé) n'est déduit que de preuves du corpus ;
règles nommées et citations à l'appui. Statuts : ACTIVE, MODIFIED, REPLACED, ABROGATED, HISTORICAL, UNKNOWN.

| Statut | Textes |
|---|---:|
| ACTIVE | 144 |
| MODIFIED | 55 |
| REPLACED | 21 |
| ABROGATED | 55 |
| HISTORICAL (périodes échues d'une série) | 30 |
| UNKNOWN (aucune relation ni période explicite dans le corpus) | 337 |
| Articles avec statut propre | 170 (3 amendements non résolus) |

Principes : une valeur plus récente **n'abroge jamais** une plus ancienne sans preuve textuelle ; « abroge ET remplace » → REPLACED ; une abrogation ou un remplacement partiel donne MODIFIED ; un texte isolé est UNKNOWN et n'est pas présenté
comme applicable. **Séries annuelles** : deux séries détectées (prime du fonds de garantie des dépôts, 23 textes, un par exercice ; seuils semestriels des taux excessifs, 9 notes). Chaque texte fixe la valeur d'**une période**
(« exercice 2012 ») : les périodes échues sont HISTORICAL, jamais ABROGATED ; la dernière période publiée est ACTIVE (avec la mention qu'une période plus récente peut exister hors corpus). Les règles sont énumérées dans `legal_status.json` (`regles`).

**Vecteurs.** 11 106 vecteurs (chunks FR + AR) de dimension 384 dans `D:\llm\index\vec_2630b697273f.npy` ; construction incrémentale par empreinte du texte du passage (cache `vec_cache_e5small.npz`).
Intégrité vérifiée : ordre des `chunk_id` identique à celui du corpus, aucun NaN, normes = 1, aucun vecteur nul, **ré-encodage de 60 chunks tirés au hasard : cosinus = 1,000000**. Les 6 chunks du document de langue indéterminée ne sont pas indexés.

**Défauts connus du corpus final (non corrigés ; à traiter avant toute nouvelle mesure, §13).**

| Défaut | Mesure | Conséquence observée |
|---|---|---|
| Identifiants de chunks non uniques (articles répétés : annexes, additifs) | 76 identifiants, 183 chunks | citation ambiguë par `chunk_id` ; comparer par position |
| Jumeaux arabes non rattachés (date erronée par l'OCR ou absente) | 12 textes ; ex. `REG-08-04-20051223` (arabe, date « 2005 » lue par l'OCR) face à `REG-08-04-20081223` | une question arabe sur 2005 reçoit la valeur de 2008 (item H117, TEST) |
| Relations d'un texte FR dont le document cible est le jumeau **arabe** | 31 relations (8 dans l'instantané précédent) | le texte modificateur n'est pas remonté (`add_modifiers`) ; simulation corrigée : jeux historiques R@5 0,853 → 0,860, benchmark humain DEV inchangé (tableau d'ablation, `tables_phase3_extra.md`) |
| Documents sans date | 27 | statut / temporalité limités |
| Chunks arabes illisibles | 4 (3 documents) | ces textes ne peuvent pas être retrouvés |

## 2. Architecture finale

```
question
  │ références explicites (type / n° / article) + relations (inchangé)
  ├─ BM25 ─────────────────┐
  ├─ e5-small (ONNX) ──────┤ fusion RRF (k=60)
  ▼                        ▼
logique juridique : date de référence, textes futurs/abrogés/remplacés, textes modificateurs remontés, chaîne de versions,
  séries périodiques (NOUVEAU), clarification des questions vagues
  ▼
reranker cross-encoder int8 (20 candidats, blend W_RERANK = 3,0)  →  refus : cos ≥ 0,855 OU score reranker ≥ −1,9   (inchangés)
  ▼
filtrage temporel / statut : versions remplacées écartées du contexte du LLM, statut juridique de chaque source (NOUVEAU)
  ▼
contexte juridique borné (6 400 caractères max.) → Qwen3-4B local (JSON contraint par schéma) → réponse + citations + avertissements de statut déterministes
```

`AGENT_RETRIEVER=legacy` reste le retour arrière (et le repli automatique si les modèles ou vecteurs manquent) ; `hybrid_rerank` reste le moteur par défaut. **Je n'ai ni remplacé `hybrid_rerank`, ni modifié le modèle d'embeddings, le reranker,
les poids de fusion, le seuil de refus ou le découpage en chunks.** La comparaison des six moteurs sur le benchmark indépendant (§4) confirme ce choix.

**Ce qui a changé en phase 3 (tout est mesuré ou documenté ci-dessous).**

| Changement | Pourquoi | Mesure |
|---|---|---|
| `legal_status.py` : statuts par texte et par article, preuves citées | exigence « jamais d'ancienne valeur présentée comme actuelle » | 10 tests ; décisions §6–7 |
| Règle de séries dans `retrieve2.py` (facteur 1,0 période demandée / 0,4 autres périodes, appliqué avant le reranker et sur le score final) | les séries annuelles ne s'abrogent pas : « en 2012 » = exercice 2012 | **gain** sur DEV (R@3 0,766 → 0,797 ; juridique@1 0,833 → 0,881 ; 2 questions) ; **perte** sur les jeux historiques (R@5 0,875 → 0,853 ; 3 questions de gold_v5 lisent « en N » comme l'année de signature). Compromis assumé et documenté. |
| Qualificatifs génériques (« applicable », « en vigueur », « actuel »…) et inversions (« est-il … ») dans la détection des questions vagues | éviter de refuser une question valide / détecter l'anaphore | tests ; clarification DEV 5/5, TEST 1/3 |
| Contexte du LLM : relations bornées (4 plus récentes par type, abrogation/remplacement partiels étiquetés « partiellement »), statut de chaque source, consignes selon la question (date historique, « actuel », plusieurs textes), règle 4 bis (le statut qualifie la réponse, ne justifie jamais un refus) | un 4B suit mal un contexte long et confond une modification avec une abrogation | DEV : réponse correcte 0,609 après correctifs de notation et de consigne (voir §14 : non attribuable à un seul changement) |
| Fournisseur LLM par défaut = **local** ; l'API distante exige `AGENT_LLM=anthropic` **et** `AGENT_ALLOW_REMOTE_LLM=1` | sécurité : « tout doit rester local » (le défaut précédent était distant) | 2 tests (défaut local ; aucune connexion non-loopback pendant recherche + génération) |
| Interface : « Sources retrouvées » puis « Réponse générée », étiquette de statut | traçabilité | test d'interface |
| `build_vectors.py` incrémental ; extraction OCR de repli ; dates ancrées ; étape `status` | corpus | tests de pipeline |

## 3. Benchmark humain (`agent_fr/eval/human/benchmark_v1_draft.jsonl`)

**130 questions** : DEV 78 / TEST 52 ; 116 en français, 14 en arabe ; 63 textes distincts attendus. Champs : id, question, langue, domaine, document attendu (avec URL officielle), article attendu, passage attendu (cité mot pour mot,
vérifié mécaniquement dans le corpus), réponse attendue, faits clés, date de référence, statut juridique, applicabilité à la date de référence, difficulté, type de question, versions interdites, validation humaine.

| Type | DEV | TEST | Total |
|---|---:|---:|---:|
| A direct (montant, seuil, délai, obligation, interdiction, définition) | 16 | 10 | 26 |
| B multi-textes | 5 | 3 | 8 |
| C temporelle (dont séries annuelles) | 18 | 11 | 29 |
| D modification | 7 | 5 | 12 |
| E abrogation | 6 | 4 | 10 |
| F comparaison ancien / actuel | 4 | 3 | 7 |
| G ambiguë (doit demander une précision) | 5 | 3 | 8 |
| H hors corpus (doit refuser) | 6 | 4 | 10 |
| I hors sujet (doit refuser) | 3 | 3 | 6 |
| J français / arabe | 8 | 6 | 14 |

Domaines : change 22, politique monétaire 19, prudentiel 17, garantie des dépôts 13, LBC/FT 8, banque digitale 4, autres. Difficulté : facile 34, moyen 74, difficile 22. Statuts attendus : ACTIVE 32, ABROGATED 16, REPLACED 14, HISTORICAL 7, MODIFIED 3, UNKNOWN 1 (57 questions sans statut attendu). Sous-benchmark de **temporalité** (types C, D, E, F et
chaînes A → B → C) : 41 questions en DEV, 29 en TEST.

**Protocole, fixé avant le split TEST.**
* Les règles de recherche et de contexte ont été réglées avec DEV ; **le split TEST n'a été exécuté qu'une fois** (2026-10-07 00:23, règles figées) ; ses sorties brutes sont gelées
  (`human_bench_test_final.json`, SHA-256 `3c9b28f00824817f9e9fd2b08ee4591c7e3858a9fb1b37191541d28793604275`, fichier en lecture seule ; `FROZEN_SHA256.txt`). Le manifeste des règles figées (30 fichiers de code + 8 fichiers du corpus, SHA-256 ; `frozen_rules_manifest.json`, `0aa5ae14…da1b`) a été écrit
  avant l'exécution ; aucun fichier du moteur ni de la notation n'a changé depuis (vérifié).
* Critères de décision GO / CONDITIONAL GO / NO-GO écrits avant TEST (`decision_criteria.md`, SHA-256 `50c804e4…ad04`).
* Règles de notation en en-tête de `bench.py` ; **aucune règle de notation n'a été modifiée après avoir vu TEST**. Les défauts de notation trouvés sur DEV (statut, C2/C5 qui ignoraient les métadonnées, chiffres arabo-indiens, k=10 pour Recall@10) ont été corrigés **avant** le gel
  et sont listés au §14 : ils changent les chiffres de DEV (réponse correcte 0,312 → 0,609 entre la run 1 et la run 2, en partie à cause de ces corrections et non du seul système).
* Questions à relire par un juriste : paquet `review/benchmark_review.html` (+ `.csv`) ; évaluation humaine de 60 réponses (échantillon stratifié, graine 7) : `review/human_eval.html`. Ingestion : `packs ingest-review` / `ingest-eval`
  (calcul de l'accord et des divergences avec la notation automatique **sans** modifier les règles). **Rien de tout cela n'a été fait : il faut un humain.**

**Jeux d'évaluation : à ne pas mélanger.**

| Jeu | Taille | Statut | Mesure dans ce rapport |
|---|---:|---|---|
| gold_v2 (+ `oos`) | 62 | écrit par IA ; utilisé pour **régler** l'ancien moteur (historique) | re-mesure retrieval seul sur le corpus final (§4) |
| gold_v3, gold_v4 | 41 + 26 | écrits par IA ; consultés pour corriger des défauts en phase 2 (**développement**) | idem |
| gold_v5 | 45 | écrit par IA ; aveugle pour la 1re passe de la phase 2, consulté ensuite | idem |
| Phase 2 : 136 questions retrieval / 112 bout en bout | — | v2–v5 réunis | chiffres de la phase 2 conservés tels quels dans `RETRIEVAL_PHASE2.md` |
| **Benchmark humain DEV** | 78 | écrit par IA, **non validé par un humain** ; **utilisé pour régler** la phase 3 | §4–5 (non aveugle) |
| **Benchmark humain TEST** | 52 | écrit par IA, **non validé par un humain** ; **non utilisé pour régler**, exécuté une fois | §4–5 (aveugle pour les règles ; non validé humainement) |

## 4. Résultats retrieval (moteur `hybrid_rerank`, retrieval seul pour la comparaison ; classement k = 10)

Questions à réponse attendue : DEV 64, TEST 42. Intervalles de Wilson à 95 % dans `tables_phase3_extra.md` (ex. Recall@5 TEST 0,714 [0,564 ; 0,828]) : **les effectifs sont petits et DEV / TEST ne sont pas significativement différents sur chaque métrique prise seule.**

| Mesure | DEV | TEST |
|---|---:|---:|
| Recall@1 | 0,641 (41/64) | 0,500 (21/42) |
| Recall@3 | 0,797 (51/64) | 0,619 (26/42) |
| Recall@5 | 0,828 (53/64) | 0,714 (30/42) |
| Recall@10 | 0,859 (55/64) | 0,762 (32/42) |
| MRR | 0,723 | 0,582 |
| Texte@1 / @5 | 0,703 / 0,891 | 0,595 / 0,786 |
| Article@1 / @5 | 0,621 / 0,810 | 0,500 / 0,714 |
| Exactitude temporelle@1 | 0,667 (28/42) | 0,517 (15/29) |
| Exactitude juridique@1 | 0,881 (37/42) | 0,793 (23/29) |

**TEST est moins bon que DEV** sur toutes les mesures de classement (Recall@5 −11,4 points, MRR −14,1 points) : c'est le signe attendu d'un réglage sur DEV, auquel s'ajoutent la petite taille des échantillons et les types C et D, nettement moins bien retrouvés en TEST
(Recall@5 : C 0,636 contre 0,944 ; D 0,400 contre 1,000). Le chiffre à retenir comme estimation hors réglage est celui de TEST.

**Comparaison des six moteurs sur le même benchmark** (retrieval seul ; détail et tableaux complets dans `tables_phase3_extra.md`) :

| Moteur | Recall@5 DEV | MRR DEV | Recall@5 TEST | MRR TEST | Refus corrects DEV / TEST | Clarifications DEV / TEST |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 0,656 | 0,547 | 0,500 | 0,422 | 3/9 · 2/7 | 0/5 · 0/3 |
| bm25 | 0,656 | 0,510 | 0,500 | 0,417 | 2/9 · 2/7 | 0/5 · 0/3 |
| vector | 0,688 | 0,481 | 0,595 | 0,523 | 9/9 · 7/7 | 0/5 · 0/3 |
| hybrid_plain | 0,734 | 0,544 | 0,595 | 0,511 | 9/9 · 7/7 | 0/5 · 0/3 |
| hybrid | 0,812 | 0,646 | 0,690 | 0,517 | 9/9 · 7/7 | 5/5 · 1/3 |
| **hybrid_rerank** | **0,828** | **0,723** | **0,714** | **0,582** | 8/9 · 6/7 | 5/5 · 1/3 |

`hybrid_rerank` est le meilleur ou à égalité en Recall@1/3/5 et en MRR sur DEV **et** TEST ; l'ancien moteur est nettement derrière (Recall@5 TEST 0,500 contre 0,714). Aucun changement de moteur n'est justifié.
Le classement est calculé sur une recherche à k = 10 ; la liste de production (k = 6, celle donnée au LLM) donne **les mêmes Recall@1/3/5** sur DEV et TEST (MRR 0,719 / 0,581) : le choix de k ne change pas les conclusions.

**Re-mesure des jeux historiques sur le corpus final** (136 questions, retrieval seul, identifiants remappés par empreinte de fichier ; non strictement comparable à la phase 2) :

| `hybrid_rerank` | Phase 2 (corpus 2026-10-06) | Phase 3 (corpus final) |
|---|---:|---:|
| Recall@1 / @5 | 0,684 / 0,890 | 0,654 / 0,853 |
| MRR | 0,770 | 0,742 |
| Faux refus / refus corrects / clarifications | 1/136 · 28/30 · 8/8 | 1/136 · 28/30 · 8/8 |
| Texte périmé en tête | 2/28 | 3/28 |
| `legacy` Recall@5 / MRR | 0,765 / 0,638 | 0,765 / 0,637 |

Six questions se dégradent (une s'améliore) : trois (X019, X026, X028, prime annuelle) à cause de la règle de séries (« en 2012 » lu comme exercice 2012, alors que le gold v5 attend l'année de signature) ; une (G038) à cause de la relation FR → jumeau arabe (§1) ;
une arabe (V041, texte REG-25-07 sans articles détectés par l'OCR) ; une (W007) de rang 1 à 2. **La finalisation du corpus et de la logique de séries coûte donc ≈ 3,7 points de Recall@5 sur les jeux historiques (5 questions sur 136)** : 3 questions pour la règle de séries (mesuré en la désactivant : R@5 0,875), 1 pour le défaut de relations (mesuré par simulation : R@5 0,860), 1 pour le texte arabe REG-25-07.

**Par type (TEST ; DEV dans `tables_phase3.md`).**

| Type | n | Recall@5 | MRR | Temporel@1 | Réponse correcte (auto) |
|---|---:|---:|---:|---:|---:|
| A direct | 10 | 0,900 | 0,850 | — | 0,800 |
| B multi-textes | 3 | 0,667 | 0,178 | 0,667 | 0,333 |
| C temporelle | 11 | 0,636 | 0,591 | 0,545 | 0,455 |
| D modification | 5 | 0,400 | 0,265 | 0,200 | 0,200 |
| E abrogation | 4 | 1,000 | 1,000 | 1,000 | 0,750 |
| F comparaison | 3 | 0,667 | 0,283 | 0,333 | 0,667 |
| J français / arabe | 6 | 0,667 | 0,458 | 0,333 | 0,333 |

Les questions de **modification (D)** et **multi-textes (B)** sont les points faibles du retrieval : le moteur retrouve un texte, rarement toute la chaîne.

**Français / arabe** (14 questions arabes avec leur jumeau français, DEV + TEST) : Recall@5 arabe 10/14 contre 11/14 pour les jumeaux français (parité du retrieval) ; réponse correcte (notation automatique) arabe 3/14 contre 9/14 en français. L'écart est dans la **réponse**, pas dans la recherche : voir §8.

## 5. Résultats LLM (Qwen3-4B local, k = 6, JSON contraint)

| Mesure | DEV (64 + 14 sans réponse) | TEST (42 + 10 sans réponse) |
|---|---:|---:|
| Retrieval correct (top-5) | 0,828 (53/64) | 0,714 (30/42) |
| Contexte suffisant | 0,828 | 0,667 (28/42) |
| C1 répond (faits clés) | 0,797 | 0,690 |
| C2 soutenue par les sources citées | 0,844 | 0,738 |
| C3 bonne version | 0,766 | 0,643 |
| C4 citation correcte | 0,766 | 0,619 |
| C5 rien hors contexte | 0,922 | 0,929 |
| **Réponse correcte (C1–C5)** | **0,609 (39/64)** | **0,524 (22/42)** |
| Statut juridique correct | 0,846 (33/39) | 0,783 (18/23) |
| Hallucination (auto) | 0,125 (8/64) | **0,143 (6/42)** |
| Refus à tort | 0,109 (7/64) | 0,143 (6/42) |
| Erreur temporelle critique | 0,035 (2/57) | **0,000 (0/35)** |
| Refus corrects (hors corpus + hors sujet) | 1,000 (9/9) | 0,857 (6/7) |
| Question à refuser mais traitée | 0/9 | 1/7 |
| Clarification demandée (ambiguës) | 1,000 (5/5) | **0,333 (1/3)** |

Une réponse n'est comptée correcte que si elle répond (C1), est soutenue par les sources citées (C2), utilise la bonne version (C3), cite correctement (C4) et n'ajoute rien hors contexte (C5) ; la notation est automatique et stricte (règles dans `bench.py`).
« Hallucination (auto) » est un **indicateur** (réponse non soutenue par ses sources ou nombre / article absents du contexte), pas un jugement humain.

**Relecture IA (non humaine) des réponses rejetées** (`ai_adjudication.json`, 25 en DEV, 20 + 3 en TEST). La notation automatique est stricte ; plusieurs réponses rejetées sont correctes sur le fond (formulation, article voisin, source alternative).

| Split | Auto | Estimation IA (auto + rejetées jugées correctes ou correctes avec défaut) | Estimation IA haute (+ sources à arbitrer) |
|---|---:|---:|---:|
| DEV | 39/64 = 0,609 | 47/64 = 0,734 | 48/64 = 0,750 |
| TEST | 22/42 = 0,524 | 27/42 = 0,643 | 29/42 = 0,690 |

Cette estimation est une **borne haute** : seules les réponses rejetées ont été relues, les réponses jugées correctes par la machine ne l'ont pas été. Elle ne remplace pas l'évaluation humaine.

**Causes des échecs relus** (DEV + TEST ; table complète avec définitions dans `tables_phase3_extra.md`) :

| Cause | DEV | TEST |
|---|---:|---:|
| Mauvais texte non retrouvé (RETR_DOC) | 6 | 4 |
| Bon texte, mauvais article / article de la valeur absent (RETR_ART) | 1 | 2 |
| Refus du moteur de recherche alors que la réponse existe (RETR_REFUS) | 0 | 1 |
| Le LLM refuse alors que le passage est dans son contexte (LLM_REFUS) | 3 | 2 |
| Le LLM nomme le mauvais texte d'une chaîne (LLM_CHAIN) | 1 | 2 |
| OCR arabe (chiffres, mots, passage tronqué) | 4 | 1 |
| Date de référence interne reprise comme venant des sources (HINT_LEAK) | 2 | 2 |
| Notation trop stricte (SCORER) / nombre calculé (DERIVED_NUMBER) | 4 / 3 | 3 / 0 |
| Source attendue à arbitrer (GOLD_ARB) | 1 | 2 |
| Question ambiguë non détectée / hors corpus traitée / identité du texte | 0 / 0 / 0 | 2 / 1 / 1 |

**Divergences notation automatique ↔ lecture IA (à confirmer par un humain).** (1) Des réponses correctes sont rejetées (notation trop stricte : 7 en DEV, 3 en TEST ; 3 autres cas sont des sources alternatives à arbitrer). (2) L'indicateur « hallucination » compte des cas qui ne sont pas des inventions juridiques :
chiffre calculé par le modèle (différence 5,75 = 9,5 − 3,75), chiffres écrits en lettres puis en chiffres. (3) Mais il compte aussi une **vraie dérive à corriger** : dans 4 réponses (2 DEV, 2 TEST) le modèle écrit une date de référence (« 31 décembre 1995 », « 30 juin 1998 »…) : la date vient de la consigne interne, pas des sources.
Aucune règle de notation n'a été modifiée pour ces cas.

## 6. Erreurs temporelles

**Aucune ancienne valeur n'a été présentée comme actuelle en TEST (0 / 35)** ; en DEV 2 / 57 (intervalle de Wilson à 95 % TEST : 0 – 9,9 %). Les deux erreurs critiques de DEV sont **arabes** (H129 : taux des réserves obligatoires « actuel » donné par la version de 2021 ; H130 : taux directeur « 902.75 % » tiré d'une
instruction remplacée), toutes deux causées par l'OCR (§8) : la version actuelle en arabe est illisible (« د 1 % », « 2,50 ١ %o »).

Exactitude temporelle@1 : DEV 0,667 (28/42), TEST 0,517 (15/29) ; exactitude juridique@1 : 0,881 / 0,793. Statut juridique correct : 0,846 / 0,783 ; dans les 11 cas d'erreur (6 en DEV, 5 en TEST), la lecture IA montre surtout un texte différent du texte attendu (mauvais texte retrouvé, questions multi-textes ou de modification) ;
je n'ai pas vérifié chaque cas contre les relations du corpus. Le statut attendu a été fixé par l'IA en lisant les textes puis recoupé avec le module : **l'accord n'est donc pas indépendant** ; seule la validation humaine peut le garantir.

Sous-benchmark de temporalité (chaînes Texte A → B modifie A → C modifie B → état actuel ; valeur ancienne / actuelle, date d'entrée en vigueur, texte modificateur, texte abrogeant, article remplacé, article partiellement modifié) :

| Mesure | DEV (n = 41) | TEST (n = 29) |
|---|---:|---:|
| Recall@1 | 0,585 (24/41) | 0,414 (12/29) |
| Exactitude temporelle@1 | 0,683 | 0,517 |
| Exactitude juridique@1 | 0,878 | 0,793 |
| Réponse correcte | 0,561 | 0,448 |
| Statut correct | 0,861 (31/36) | 0,783 (18/23) |
| Erreurs temporelles critiques | 0,056 (2/36) | 0,000 (0/23) |

Points faibles mesurés : (a) questions à date de référence : le bon texte est classé premier et aucune version interdite n'est en tête dans 15 / 29 cas en TEST (28 / 42 en DEV) ; (b) **chaîne de modifications** : le système retrouve souvent la dernière modification mais pas la chaîne complète ; (c) **le texte actuel n'est pas retrouvé** pour
« capital minimum d'une banque aujourd'hui » (REG-24-02 ; H036, TEST) alors qu'il est actif.
Un texte UNKNOWN n'est jamais affiché comme applicable : l'étiquette `statut_juridique` et les avertissements de statut sont déterministes (tests). Cette propriété n'est pas mesurée comme un taux sur le benchmark (« non mesuré »).

## 7. Erreurs d'abrogation

* **Chaîne d'abrogation mal attribuée (TEST, H078)** : « le règlement 2004-01 a-t-il été abrogé, et par quel texte ? » → le modèle répond « par le règlement 2018-03 » ; le bon texte est 2008-04 (art. 5), le 2018-03 abroge 2008-04 (art. 5). Le contexte contenait la bonne source en tête ; **le LLM a nommé le dernier texte de la chaîne** (mélange de relations).
* **Abrogation partielle** : en DEV 1, une abrogation partielle était présentée comme totale (« le règlement 07-01 est abrogé ») ; corrigé avant TEST par l'étiquette « Abrogé partiellement par » dans le contexte (le texte reste MODIFIED).
* **Abrogation d'un texte non retrouvé** : H084 (DEV) : l'instruction 09-2025 (REPLACED) est dans le contexte mais le texte qui la remplace n'est pas retrouvé ; le modèle refuse au lieu de signaler le remplacement.
* Les 4 questions E de TEST ont un Recall@5 de 1,000 et une réponse correcte pour 3 sur 4 ; les 6 de DEV : 5 sur 6 (la 6e est un refus à tort).
* Séries : aucune période n'est déclarée abrogée par une période plus récente ; chaque période échue est HISTORICAL (test dédié `test_periodic_series_older_periods_are_historical_not_abrogated`).
* Statut ABROGATED : 55 textes dont la preuve est l'intitulé (confiance HIGH) ou le texte d'un texte ultérieur (confiance MEDIUM, citation à l'appui) ; aucun statut n'est déduit de l'ordre des dates (test `test_newer_value_never_abrogates_without_evidence`).

## 8. Erreurs OCR et arabe

Les erreurs arabes sont analysées **séparément** (arabe natif / OCR / mixte, §1 pour les audits) et jamais « corrigées » par le modèle d'embeddings : lorsque l'OCR est la cause, la correction relève de la chaîne OCR.

| Observation (relecture IA) | Items | Nature |
|---|---|---|
| Chiffres altérés dans le texte arabe : « 902.75 » pour « 2,75 % », « د 1 % », « 2,50 ١ %o » | H129, H130 (DEV) | erreur de chiffre → réponse fausse ou texte actuel non retrouvé |
| Passage tronqué : le délai de domiciliation n'est pas dans l'article 2 arabe | H121 (DEV) | OCR / segmentation |
| Mot altéré (« رصيد عدين » pour « رصيد مدين ») + refus du modèle | H120 (DEV) | OCR |
| Phrase du signataire unique mêlée de caractères latins | H118 (TEST) | OCR |
| Millésime lu « 2005 » pour 2008 → jumeau arabe non rattaché | H117 (TEST) | identité du texte |
| Exercice 2012 mal rattaché | H128 (DEV) | retrieval arabe (séries) |

Sur l'ensemble : **10 des 14 questions arabes ont le bon texte dans le top-5**, mais la réponse automatiquement correcte tombe à 3/14 (5/14 après relecture IA des échecs, 6/14 en comptant H119 à arbitrer). Cause dominante : la qualité du texte arabe lui-même (nombres : rappel moyen 0,85 ; 70 numéros d'article non numériques sur 2 512 ; 4 chunks illisibles), puis la génération en arabe par un modèle de 4 milliards de paramètres.
La conformité des **chiffres, dates, numéros d'article, noms propres et termes juridiques** a été mesurée par l'audit (rappel des nombres et des années, termes juridiques moyens 0,336) ; les noms propres ne sont pas mesurés.
**Corriger la chaîne OCR** : (1) modèle `tessdata_best` pour l'arabe (autorisation de téléchargement requise) ; (2) vérification humaine ciblée des 7 documents dont le rappel des nombres est < 50 % ; (3) comparer systématiquement chiffres et dates au jumeau français quand il existe, et **signaler** (jamais corriger automatiquement) toute divergence.

## 9. Performances (i7-13700, 24 threads, 15,6 Go de RAM, sans GPU ; llama-server chargé)

| Mesure | Phase 2 | Phase 3 (corpus final) |
|---|---:|---:|
| Corpus : documents / chunks / vecteurs | 1 073 / 10 815 / 10 814 | 1 085 / 11 112 / 11 106 |
| Taille du fichier de vecteurs courant | 17,0 Mo | 17,1 Mo (le dossier d'index conserve aussi des versions antérieures : 138 Mo en tout) |
| RAM agent (modèles chargés) | 1 667 Mo | 1 671 Mo |
| RAM llama-server (Qwen3-4B Q4_K_M) | 3 007 Mo | 3 018 Mo |
| Retrieval `hybrid_rerank`, total moyen / p95 | 893 / 1 391 ms | 503 / 721 ms |
| dont embedding de la question / recherche / reranking (moyennes) | 23 / 4 / 864 ms | 7 / 5 / 489 ms |
| Premier appel (chargement) | 1,22 s | 1,21 s |
| LLM par appel, DEV : moyenne / médiane / p95 / max | — | 33,5 / 30,1 / 53,2 / 72,4 s |
| LLM par appel, TEST | — | 39,3 / 34,5 / 76,2 / 96,5 s |
| Total par question (retrieval + LLM) DEV : moyenne / médiane / p95 | — | 28,5 / 28,4 / 52,6 s |

La baisse du temps de retrieval entre la phase 2 et la phase 3 **n'est pas une optimisation** : la mesure de la phase 2 avait été faite pendant que le crawl tournait en arrière-plan, celle-ci sur une machine au repos. La croissance du corpus (+ 2,7 % de chunks) n'a pas de coût mesurable.
La génération (≈ 30 s) domine : 98 % du temps de réponse ; aucune optimisation prématurée n'a été tentée.

## 10. Sécurité : tout reste local

* Embeddings (e5-small ONNX), reranker (mmarco int8), Qwen3-4B (llama.cpp sur `127.0.0.1:8187` : vérifié, le port n'écoute que sur la boucle locale), corpus, vecteurs : sur la machine (`D:\llm`). Aucun document du corpus n'est publié dans un Artifact ni envoyé à un service externe.
* Le fournisseur par défaut est **local** ; le fournisseur distant exige deux conditions explicites (`AGENT_LLM=anthropic` et `AGENT_ALLOW_REMOTE_LLM=1`) et reste désactivé. Tous les runs de ce rapport utilisent `AGENT_LLM=local`.
* Test automatique `test_no_non_loopback_network_connection_during_retrieval_and_generation` : aucune connexion hors boucle locale pendant recherche + génération ; 44 tests passent (agent 25, pipeline 9, statut juridique 10).
* Les paquets de relecture humaine sont des fichiers HTML locaux, sans réseau.
* Aucune clé d'API n'est présente dans le code ni dans les fichiers de résultats.

## 11. Limites

1. **Le benchmark n'est pas validé par un humain** (130 / 130 « en attente ») : questions, passages, réponses et statuts attendus ont été rédigés par la même IA que celle qui a bâti le système. Risque de biais partagé ; la validation humaine est le préalable à tout GO.
2. **L'évaluation humaine de 60 réponses n'a pas eu lieu** ; les divergences avec la notation automatique ne sont connues que par lecture IA des seuls échecs.
3. **TEST n'a que 52 questions** (42 à réponse attendue ; 3 questions ambiguës, 7 hors corpus / hors sujet) : intervalles larges (ex. refus corrects 6/7 : [0,49 ; 0,97] ; clarification 1/3). DEV a été utilisé pour régler : ses chiffres sont optimistes.
4. **TEST est consommé** : toute correction du moteur doit être mesurée sur un **nouveau** jeu de test (une re-mesure sur ce TEST ne serait plus aveugle).
5. Les chiffres de DEV de la run 2 mélangent l'effet du système et celui de corrections de notation faites avant le gel (§14).
6. Le corpus est ce que le site expose : 38 liens morts, 12 jumeaux arabes non rattachés, 27 documents sans date, 337 textes de statut UNKNOWN (aucune relation prouvable) ; « actuel » = « version la plus récente du corpus ».
7. L'arabe reste faible à cause de l'OCR (§8) ; le modèle de 4 milliards de paramètres génère moins bien en arabe qu'en français.
8. Points faibles du moteur : questions de modification et multi-textes (Recall@5 TEST de 0,400 pour D), classement des articles à l'intérieur d'un même texte (valeur à l'article 2, échéance à l'article 3), refus à tort du LLM alors que le passage est dans le contexte (6 / 42 en TEST), questions ambiguës nouvelles non détectées (TEST 1/3), question hors corpus traitée (« allocation familiale », TEST).
9. Le statut attendu du benchmark vient du module de statut puis d'une lecture IA : accord non indépendant.

## 12. Décision

**Décision : NO-GO au sens des critères pré-enregistrés** (`decision_criteria.md`, écrits avant TEST, non modifiés). Aucune métrique ne décide seule ; le tableau ci-dessous reprend tous les critères.

| Critère (TEST, 42 questions à réponse attendue ; 52 au total) | Seuil GO | Seuil CONDITIONAL GO | Seuil NO-GO | Mesuré | Verdict |
|---|---|---|---|---:|---|
| Erreurs temporelles critiques (questions « actuel ») | 0 | ≤ 10 % | > 10 % | 0 / 35 | GO |
| Hallucination automatique | ≤ 5 % | ≤ 10 % | **> 10 %** | **14,3 % (6/42)** ; DEV 12,5 % | **NO-GO** (DEV et TEST concordent) |
| Refus corrects (hors corpus + hors sujet) | ≥ 90 % | ≥ 80 % | < 80 % | 85,7 % (6/7) ; DEV 9/9 | CONDITIONAL GO |
| Réponse correcte (questions à réponse attendue) | ≥ 70 % | — | — | 52,4 % (DEV 60,9 %) | GO non atteint |
| Validation humaine complète (≥ 90 % du benchmark + ≥ 50 réponses évaluées) | exigée | absente tolérée avec mention | — | absente | GO impossible |
| Aucune donnée ne quitte la machine | — | exigée | NO-GO sinon | vérifié | conforme |
| Statut UNKNOWN jamais présenté comme actuel sans signalement | exigé | — | — | non mesuré en taux (tests déterministes) | non vérifiable |

**Pourquoi NO-GO et pas CONDITIONAL GO.** Le seul critère de CONDITIONAL GO non atteint est l'hallucination automatique (14,3 % contre ≤ 10 %), et il l'est sur **les deux splits** (12,5 % en DEV, 14,3 % en TEST ; intervalle TEST [6,7 % ; 27,8 %] : 10 % n'est pas exclu statistiquement). Il est corroboré par la réponse correcte (52 % contre 70 % pour un GO),
par la clarification des questions ambiguës (1/3) et par une question hors corpus traitée (1/7). Deux des six « hallucinations » de TEST sont la dérive de la date de référence (HINT_LEAK) et non une invention juridique. **Sans elles, le taux serait de 4/42 = 9,5 %, sous le seuil de 10 % : le NO-GO ne tient donc qu'à deux réponses, et à un seuil fixé avant la mesure.**
Je ne modifie pas la règle pour améliorer le score ; je signale cette sensibilité pour que le juriste arbitre.

**Ce que ce NO-GO ne dit pas** : il ne dit pas que l'architecture est mauvaise (zéro erreur temporelle critique en TEST, refus des questions hors sujet 3/3, `hybrid_rerank` meilleur moteur sur les deux splits, tout local) ni qu'un fine-tuning est nécessaire ; il dit que l'agent **ne doit pas être utilisé comme source d'avis juridique**,
que ses réponses rédigées doivent être vérifiées contre les passages cités (qui restent la partie fiable de l'interface : texte, article, date, statut, lien officiel), et que le benchmark doit être validé par un juriste avant de conclure plus favorablement.

**Pour passer à CONDITIONAL GO** : corriger la dérive de date (consigne), la détection de questions ambiguës et le traitement de « hors corpus » à seuil de refus constant ; **mesurer sur un nouveau jeu de test** (le TEST actuel est consommé) ; obtenir la validation humaine du benchmark.
**Pour passer à GO** : validation humaine complète, hallucination ≤ 5 %, réponse correcte ≥ 70 %, refus ≥ 90 %, avec 0 erreur temporelle critique.

**Fine-tuning : toujours non.** Les 48 échecs relus se répartissent ainsi : retrieval 14 (mauvais texte 10, mauvais article 3, refus du moteur 1), contexte et consigne 12 (date de référence 4, refus du LLM 5, chaîne de textes 3), notation et sources à arbitrer 13, OCR arabe 5,
détection des ambiguïtés et des questions hors corpus 3, identité du texte dans le corpus 1 ; aucun ne vient d'un manque de connaissance du texte juridique,
qui doit rester dans le corpus. Un fine-tuning ne pourrait viser que le comportement (refus, format) et seulement après avoir prouvé que la recherche, le contexte, la consigne, la sortie structurée, la validation et le post-traitement ne suffisent pas.

## 13. Prochaines étapes (par priorité ; rien n'est lancé avant validation humaine)

1. **Validation humaine du benchmark** (P0) : le juriste ouvre `review/benchmark_review.html`, valide ou corrige chaque question (≥ 90 %), puis évalue 60 réponses dans `review/human_eval.html` ; `packs ingest-review` / `ingest-eval` re-notent les **sorties gelées** (pas de ré-exécution) et documentent les divergences.
2. **Corrections de corpus** (chaîne, pas embeddings) : rattacher les 12 jumeaux arabes (type + numéro + année, en signalant tout écart de date) ; repointer les 31 relations vers le document FR ; suffixer les `chunk_id` dupliqués ; indexer les chunks de langue indéterminée ; en cas de divergence de date entre OCR et intitulé du site, ne pas trancher en silence.
3. **OCR arabe** : avec votre autorisation explicite, télécharger `tessdata_best` (ara) et mesurer avant / après sur les 7 documents à rappel < 50 % ; vérification humaine ciblée ; comparaison systématique des chiffres au jumeau français.
4. **Consignes du contexte** (après validation) : formuler la date de référence comme « au cours de l'année N » au lieu d'une date inventée ; refuser de conclure sur la date d'entrée en vigueur sans source ; détection des questions ambiguës génériques (« quelle est la procédure à suivre ? ») ; **mesurer chaque changement sur DEV puis sur un nouveau TEST**.
5. **Retrieval ciblé** : classement des articles à l'intérieur d'un texte (valeur vs échéance), chaînes de modifications (D), questions multi-textes (B), lecture de « en N » pour les séries (décision de gold à prendre avec le juriste).
6. **Nouveau TEST indépendant** (≥ 100 questions rédigées par le juriste, jamais vues par le système) avant toute nouvelle décision.

## 14. Journal des modifications et protocole (transparence)

Modifications **informées par DEV** (listées parce que DEV n'est donc plus aveugle) :
1. Règle 4 bis du prompt : le statut juridique qualifie la réponse et ne justifie jamais un refus (refus à tort de questions historiques vus en DEV, run 1).
2. Relations du contexte : « abrogé / remplacé partiellement » étiqueté comme tel (une modification partielle était présentée comme abrogation).
3. Notation, **corrigée avant le gel** : sémantique du statut (sujet pour E / D, dernier passage pour B / F), C2 / C5 tiennent compte du bloc de métadonnées donné au modèle (statut, relations), chiffres arabo-indiens, k = 10 pour Recall@10. Ces corrections expliquent une part importante du passage de la run 1 à la run 2 en DEV (réponse correcte 0,312 → 0,609 ; C2 0,531 → 0,844 ; C5 0,688 → 0,922 ; hallucination auto 0,484 → 0,125) **et ne sont pas des gains du système**.
4. Erreurs de rédaction du gold trouvées par le module de statut avant TEST (ex. REG-24-03 modifié par REG-25-14 ; échéance de REG-18-03 modifiée par REG-20-08 ; statuts REPLACED / ABROGATED corrigés) : correction d'items, jamais de la notation.

Modifications **non informées par DEV** : sécurité par défaut (local), extraction / OCR / dates, `build_vectors` incrémental, `legal_status.py` (conçu sur les règles du corpus et les jeux historiques), interface.

Constats **après le gel de TEST** (aucun changement de code ni de corpus depuis ; vérifié par empreintes) : comparaison des six moteurs, sensibilité k = 6 / k = 10, re-mesure des jeux historiques, ablation du facteur de série, simulation du repointage des relations, performances, intégrité des vecteurs, relecture IA. Aucune de ces mesures n'a servi à modifier le moteur.

Limite de méthode reconnue : le runner utilise une recherche à k = 10 pour le classement et une autre à k = 6 pour le contexte du LLM ; les deux listes diffèrent pour 29 questions sur 130 (surtout en queue de liste) ; effet sur les métriques mesuré : nul sur Recall@1/3/5 (§4).

## 15. Reproduire

```
# corpus final et vecteurs (déjà faits ; instantané figé : D:\llm\snapshots\corpus_phase3_final)
python -m boa_pipeline status ; python -m boa_pipeline vectors
# benchmark humain (corpus figé, LLM local) ; TEST : une seule fois
set AGENT_CORPUS_DIR=D:/llm/snapshots/corpus_phase3_final
python -m agent_fr.eval.human.run_bench --bench agent_fr/eval/human/benchmark_v1_draft.jsonl --split DEV --pipeline hybrid_rerank --tag dev_final2
python -m agent_fr.eval.human.score --bench agent_fr/eval/human/benchmark_v1_draft.jsonl --run agent_fr/eval/results/human_bench_dev_final2.json
python -m agent_fr.eval.human.make_tables3 --scores dev=agent_fr/eval/results/human_score_dev_final2.json test=agent_fr/eval/results/human_score_test_final.json
python -m agent_fr.eval.human.make_tables3_extra
python -m agent_fr.eval.regression_phase3 --pipelines hybrid_rerank legacy
python -m agent_fr.eval.perf_bench --n 40 --tag perf_phase3
python tests/test_agent.py ; python tests/test_pipeline.py ; python tests/test_legal_status.py     # sans exporter AGENT_CORPUS_DIR
```

Fichiers : `agent_fr/eval/human/` (benchmark, notation, paquets de relecture, critères de décision, manifeste des règles figées, relecture IA), `agent_fr/eval/results/human_*` (sorties brutes et notées), `docs/tables_phase3.md`, `docs/tables_phase3_extra.md`.
