# Phase 2 — Recherche juridique locale (hybride + logique temporelle + reranker)

Objectif : retrouver les bons passages juridiques **avant** de les donner au LLM local (Qwen3-4B), sans fine-tuning, sans rien envoyer hors de la machine.
Pipeline : `Corpus local → recherche locale (BM25 + vecteurs) → reranking local → Qwen local → réponse + citations`.
Toutes les valeurs ci-dessous sont **mesurées** (fichiers dans `agent_fr/eval/results/`, tableaux régénérables par `python -m agent_fr.eval.make_tables`).
Une cellule « non mesuré » signifie qu'aucune mesure n'existe : jamais d'estimation.

> **Avertissement permanent.** Les jeux de questions (v2, v3, v4, v5) ont été écrits et relus par un assistant IA (Claude) contre le texte extrait du corpus,
> **pas par un juriste humain**. Les réponses attendues sont vérifiées mécaniquement (le passage existe et contient le fait clé), mais ni le choix des questions
> ni l'interprétation juridique n'ont été validés par un humain. Statut des textes : toujours « STATUT À VÉRIFIER » sauf abrogation prouvée par un intitulé officiel.

## 1. Résumé exécutif

* **Architecture conservée : `hybrid_rerank`** (hybride BM25 + e5-small, logique juridique, reranker) comme moteur par défaut, avec **repli automatique sur l'ancien moteur**
  (`legacy`) si les modèles ou les vecteurs sont absents ; `AGENT_RETRIEVER=legacy` force le retour arrière. Rien n'est supprimé.
* Retrieval (136 questions, 6 pipelines, même corpus figé) : Recall@5 **0,765 → 0,890**, MRR **0,638 → 0,770**, Recall@1 0,522 → 0,684, questions valides refusées à tort 11 → 1,
  ambiguës détectées 0/8 → 8/8, textes périmés en tête 5/28 → 2/28.
* Bout en bout (112 questions v3+v4+v5, Qwen3-4B local) : exactitude **0,589 → 0,857** (notation automatique stricte) ; **0,670 → 0,893** après relecture IA des échecs.
* **Ce qui n'a pas progressé** : sur le jeu d'origine `gold_v2` (62 questions, sur lequel l'ancien moteur avait été réglé) l'agent complet donne 45/62 avant et 45/62 après
  (8 questions améliorées, 8 dégradées) ; les questions factuelles très lexicales (5 questions) sont moins bien classées (MRR 0,55 contre 1,0) ; l'arabe reste faible (OCR) ;
  le reranker ajoute ≈ 0,9 s par question.
* **Fine-tuning : non nécessaire aujourd'hui.** Les deux défauts d'origine (refus exact, JSON strict) sont réglés par consigne + décodage contraint par schéma + post-traitement
  (jeu aveugle 38/40 → 39/40). Les erreurs restantes viennent surtout de la recherche et de la qualité du corpus/OCR (voir §11).
* **Limite majeure** : les chiffres finaux de bout en bout ne sont **pas aveugles** (les jeux v3–v5 ont été consultés pour corriger des défauts, voir §4). Une mesure vraiment
  indépendante exige un nouveau jeu rédigé par un juriste (P0).

## 2. Architecture avant / après

```
AVANT (legacy)                                   APRÈS (hybrid_rerank)
question                                         question
  │ références explicites (type / n° / article)    │ références explicites + relations (inchangé, réutilisé)
  │ BM25 (racinisation FR)                         ├─ BM25 ──────────────┐
  │ seuils lexicaux de refus                       ├─ e5-small (ONNX) ───┤ fusion RRF (k=60) → 60 candidats
  ▼                                                │                     ▼
passages                                           │  logique juridique : date de référence, textes futurs/abrogés/remplacés,
  │                                                │  textes modificateurs remontés, chaîne de versions, clarification
  ▼                                                │  reranker cross-encoder int8 sur 20 candidats (blend par rangs)
Qwen3-4B local                                     │  refus : cosinus ≥ 0,855 OU score reranker ≥ −1,9
                                                   ▼
                                                 passages (affichés d'abord, avec Document / Article / Date / Statut / Score / Source)
                                                   │ contexte LLM : versions remplacées écartées, relations bornées, consignes propres à la question
                                                   ▼
                                                 Qwen3-4B local (JSON contraint par schéma) → réponse + citations
```

Fichiers : `agent_fr/retrieve.py` (legacy, conservé), `retrieve2.py` (hybride, logique juridique, rerank), `embed.py`, `rerank.py`, `build_vectors.py`, `pipelines.py` (registre),
`agent.py` (choix du moteur + repli), `answer.py` (contexte et consignes du LLM), `app.py` (interface).

## 3. Ce qui a été installé (tout en local, sous `D:\llm`)

| Élément | Choix | Licence | Taille disque | Pourquoi |
|---|---|---|---:|---|
| Embeddings | `intfloat/multilingual-e5-small` (ONNX fp32, 384 dim, préfixes `query:` / `passage:`) | MIT | 487 Mo | multilingue FR/AR, 3,7–23 ms par question sur CPU, pas de PyTorch |
| Reranker | `mmarco-mMiniLMv2-L12-H384` cross-encoder (ONNX int8 AVX2) | Apache-2.0 | 136 Mo | multilingue, 20 passages ≈ 0,5–1,4 s sur CPU |
| Runtime | `onnxruntime` 1.30, `tokenizers` | MIT / Apache-2.0 | — | seules dépendances ajoutées |
| Vecteurs | 10 814 chunks FR+AR | — | 17 Mo (+17 Mo de cache incrémental) | |

Modèles vérifiés (empreintes) ; aucun corpus ni passage n'a été envoyé à un service externe (encodage et reranking 100 % locaux).
Qwen3-4B-Instruct-2507 Q4_K_M (3,1 Go) et llama.cpp b11411 (69 Mo) viennent de la phase précédente.

## 4. Méthode d'évaluation et honnêteté sur les jeux

| Jeu | n | Écrit | Statut |
|---|---:|---|---|
| gold_v2 | 62 | phase 1 | dev (18) a servi à régler seuils et poids ; test et holdout consultés ensuite |
| gold_v3 | 41 | avant les nouveaux pipelines | **consulté ensuite pour corriger des défauts** (relations, dates) : plus aveugle |
| gold_v4 | 26 | après réglage des seuils, avant la résolution de versions | consulté ensuite : contaminé |
| gold_v5 | 45 | juste avant la mesure finale (SHA-256 dans `gold_v5.sha256`) | **aveugle pour la première passe de retrieval** ; consulté ensuite (voir ci-dessous) |
| oos_dev | 16 | calibration | 16 questions hors corpus pour fixer les seuils de refus |

Ce qui a été corrigé *après* avoir regardé v3/v4/v5 (à lire comme du développement, pas comme de la validation) :
logique de relations par preuve textuelle (v3/v4) ; qualificatifs génériques « applicable / en vigueur… » dans la détection de question vague (v5, première passe : clarification 1/3 → 3/3) ;
seuil de refus par reranker `RR_MIN = −1,9` (calibré sur dev + oos_dev uniquement, mais motivé par les faux refus vus sur v3–v5) ;
côté LLM : compaction des relations dans le prompt, consignes de date / valeur actuelle / plusieurs textes, exclusion des versions remplacées (motivés par les échecs bout en bout v3–v5).
Chaque version intermédiaire des résultats est conservée (`retrieval_v5_*.json` = première passe aveugle ; `e2e_pass1_*`, `e2e_prev_*`, `e2e_prev2_*` = passes antérieures).

Notation automatique bout en bout (`e2e_eval.py`) : fait clé présent (comparaison littérale après normalisation des espaces), source attendue citée, refus / clarification corrects.
Elle a des **faux négatifs** (« 08% » vs « 8 % », « interdit de stipuler » vs « interdit expressément de stipuler ») et des **faux positifs** (un seul des quatre textes modificateurs cité).
`agent_fr/eval/adjudicate.py` applique, de la même façon à tous les pipelines, des règles écrites à l'avance (preuve vérifiée dans les passages cités ; rétrogradation des listes incomplètes
et des réponses hésitantes) : c'est la colonne « après relecture IA ». Elle n'est **pas** une relecture juridique humaine.

Métriques de retrieval : Recall@1/3/5/10 et MRR sur les questions avec passage attendu (pour les questions « tous les textes », tous les passages attendus doivent être retrouvés) ;
« successeur accepté » = un texte qui modifie/abroge/remplace le texte attendu compte aussi (jamais pour les questions historiques) ; refus corrects (hors corpus / hors sujet) ;
**faux refus** = question valide refusée par le moteur de recherche ; clarifications (questions ambiguës) ; « texte périmé en tête » (questions temporelles).
Le nDCG n'est pas calculé (optionnel).

## 5. Résultats

### 5.1 Tableau de comparaison exigé

Retrieval : 136 questions (v2+v3+v4+v5) ; exactitude finale : 112 questions (v3+v4+v5) avec Qwen3-4B local. Les cellules « non mesuré » ne sont pas estimées
(BM25 pur, vectoriel pur et hybride simple n'ont pas été évalués avec le LLM : ils n'ont pas été candidats à la décision).

| Pipeline | Recall@5 | MRR | Exactitude finale (auto) | Temps moyen recherche | Temps moyen bout en bout (LLM inclus) |
|---|---:|---:|---:|---:|---:|
| Recherche actuelle (BM25 + règles, avant phase 2) | 0,765 | 0,638 | 0,589 (66/112) | 1,9 ms | 28,8 s |
| BM25 pur | 0,706 | 0,587 | non mesuré | 2,2 ms | non mesuré |
| Vectorielle pure (e5-small) | 0,757 | 0,646 | non mesuré | 11,9 ms | non mesuré |
| Hybride simple (BM25 + vecteurs, RRF) | 0,838 | 0,688 | non mesuré | 14,0 ms | non mesuré |
| Hybride + logique juridique (temps, versions, refus) | 0,860 | 0,726 | 0,795 (89/112) | 13,6 ms | 20,0 s |
| Hybride + logique juridique + reranker | **0,890** | **0,770** | **0,857 (96/112)** | 1 038 ms | 23,7 s |

### 5.2 Retrieval détaillé (136 questions, moteur final)

| Pipeline | R@1 | R@3 | R@5 | R@10 | MRR | R@5 succ. accepté | Refus corrects | Faux refus | Clarif. | Périmé en tête |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 0,522 | 0,728 | 0,765 | 0,868 | 0,638 | 0,801 | 20/30 | 11/136 | 0/8 | 5/28 |
| BM25 | 0,478 | 0,654 | 0,706 | 0,824 | 0,587 | 0,750 | 15/30 | 14/136 | 0/8 | 5/28 |
| vectoriel | 0,566 | 0,728 | 0,757 | 0,824 | 0,646 | 0,794 | 26/30 | 7/136 | 0/8 | 8/28 |
| hybride simple | 0,581 | 0,772 | 0,838 | 0,882 | 0,688 | 0,860 | 26/30 | 7/136 | 0/8 | 6/28 |
| hybride + logique | 0,618 | 0,801 | 0,860 | 0,904 | 0,726 | 0,912 | 30/30 | 8/136 | 8/8 | 1/28 |
| **hybride + logique + reranker** | **0,684** | **0,838** | **0,890** | **0,926** | **0,770** | **0,941** | 28/30 | **1/136** | 8/8 | 2/28 |

Jeu **aveugle v5, première passe** (36 questions avec passage attendu ; avant la correction des qualificatifs génériques, qui ne change pas le classement) :
legacy R@1 0,50 / R@5 0,75 / MRR 0,627 ; hybride + logique 0,694 / 0,833 / 0,774 ; **hybride + logique + reranker 0,750 / 0,861 / 0,800**, refus 6/6.
Sur 100 questions v2+v3+v4 : legacy R@5 0,77 / MRR 0,642 ; hybride + reranker 0,89 / 0,756.

### 5.3 Retrieval par catégorie (MRR ; n = questions avec passage attendu)

| Catégorie | n | legacy | vectoriel | hybride simple | hybride + logique | + reranker |
|---|---:|---:|---:|---:|---:|---:|
| état actuel | 8 | 0,458 | 0,302 | 0,293 | 0,525 | **0,812** |
| historique | 19 | 0,619 | 0,768 | 0,774 | 0,853 | **0,905** |
| modification | 9 | 0,620 | 0,241 | 0,456 | 0,707 | **0,775** |
| évolutif | 5 | 0,353 | 0,262 | 0,300 | 0,700 | 0,700 |
| arabe | 13 | 0,242 | 0,615 | 0,615 | 0,615 | 0,654 |
| référence explicite | 6 | 1,0 | 0,274 | 0,533 | 0,833 | 1,0 |
| fond | 40 | 0,694 | 0,734 | 0,756 | 0,671 | 0,696 |
| direct (définition, délai, procédure, obligation) | 22 | 0,832 | 0,939 | 0,970 | 0,977 | 0,947 |
| **direct interdiction / montant** | 5 | **1,0** | 0,850 | 0,900 | 0,651 | **0,546** |
| plusieurs textes | 6 | 0,211 | 0,208 | 0,204 | 0,158 | 0,269 |

Lecture : le gain est concentré sur les questions **temporelles, de modification et ambiguës** et sur le **refus** ; sur les questions de « fond » déjà bien servies par BM25, le moteur final est
**à égalité** (0,696 contre 0,694) ; sur les questions très lexicales (interdiction, montant), il est **moins bon** que l'ancien moteur (mais n = 5) ; les questions « plusieurs textes » restent faibles
pour tous les moteurs (le classement par texte unique ne favorise pas la complétude).

Refus : le moteur final laisse passer 2 questions hors corpus sur 30 (V027 `salaire national minimum garanti`, V025 `durée maximale de la garde à vue` : cosinus ≈ 0,85, reranker > −1,9) ; le LLM les refuse ensuite
(10/10 hors corpus et 10/10 hors sujet refusés de bout en bout, pour les trois pipelines — mais au prix d'un appel LLM de ≈ 30 s et avec le risque d'une hallucination que ce jeu ne montre pas).

### 5.4 Bout en bout (Qwen3-4B local, 112 questions)

| Pipeline | Auto | v3 | v4 | v5 | Après relecture IA | Recherche | LLM / appel | Total / question |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 0,589 (66) | 20/41 | 17/26 | 29/45 | 0,670 (75) | 3,9 ms | 35,8 s | 28,8 s |
| hybride + logique | 0,795 (89) | 34/41 | 19/26 | 36/45 | 0,821 (92) | 21,9 ms | 28,7 s | 20,0 s |
| **hybride + logique + reranker** | **0,857 (96)** | 36/41 | 22/26 | 38/45 | **0,893 (100)** | 1 011 ms | 29,9 s | 23,7 s |

Par catégorie (réponses correctes / questions, notation automatique) : ambigu 0/8 → 8/8 ; arabe 0/13 → 5/13 → 10/13 ; état actuel 5/8 → 7/8 ; historique 13/19 → 16/19 ;
modification 5/9 → 8/9 ; plusieurs textes 0/6 → 2/6 → 3/6 ; hors corpus 10/10 et hors sujet 10/10 pour les trois ; directes (27 questions) : 21/27, 22/27 et 22/27, quasi à égalité.
Le moteur legacy ne sait ni demander une précision (0/8) ni ordonner des versions ; ces deux points expliquent une grande partie de l'écart ; il faut le lire ainsi.

**Agent complet sur gold_v2 (62 questions, Qwen local, snapshot figé)** — avant (legacy, prompt antérieur) / après (moteur final) :
fait clé dev 12/18 → 13/18, test 16/20 → 16/20, holdout 10/13 → 10/13 ; source attendue citée dev 11/18 → 14/18, test 16/21 → 16/21, **holdout 12/13 → 9/13** ;
refus 8/8 et 2/2 inchangés ; questions entièrement correctes 45/62 → 45/62 (8 améliorées, 8 dégradées) ; latence LLM médiane 31,4 s → 26,6 s (prompt plus court).
Sur ce jeu, le nouvel agent n'est donc **pas** mesurablement meilleur ; les dégradations viennent surtout du reranker, qui reclasse des passages valides mais voisins (G011, G014, G033, G044).

### 5.5 Erreurs restantes du moteur final (16 échecs automatiques sur 112)

| Cause | Questions | Commentaire |
|---|---|---|
| Notation littérale (réponse juste) | V006, V007, V023, W013 | récupérés par la relecture |
| Source différente mais pertinente | W005, X008, X009, V039 | texte successeur / autre texte portant la même règle (X009 : le texte attendu est classé 11ᵉ) ; récupérés (preuve dans le passage cité) |
| Retrieval : mauvais texte en tête | V012, W012, X025 | W012 (« taux 2005 » : l'instruction 01-2005 règle la *rémunération*, pas le taux), X025 (« réescompte 2012 » attiré par les instructions de réserves de 2012) |
| Série annuelle sans relation d'abrogation | X016 (prime « actuelle ») | 23 instructions annuelles de prime sans lien entre elles : « la plus récente » n'est pas déductible des relations |
| Refus du LLM malgré le bon passage | X021 | le texte dit « exercice 2023 » pour une instruction de 2024 : gold discutable |
| Complétude (plusieurs textes) | X028 (échec) ; V010, V011, X029 (jugés justes à la notation, rétrogradés à la relecture) | le modèle de 4 Md n'énumère pas tous les textes |
| Arabe | W024, X042 | OCR et recherche inter-langues |

## 6. Analyse du retrieval

* **BM25 seul** (0,706 R@5) et **vecteurs seuls** (0,757) sont proches ; leur fusion (RRF) apporte l'essentiel du gain de rappel (0,838) : les deux se trompent sur des questions différentes.
  Les vecteurs seuls sont bons pour le refus (26/30) et l'arabe, mauvais pour les références (« article 5 du règlement 14-02 ») et les évolutions : la logique de références/relations reste indispensable.
* **La logique juridique** ne change presque pas le rappel mais change *quel texte est en tête* : textes périmés en tête 6/28 → 1/28, refus 26/30 → 30/30, clarifications 0/8 → 8/8,
  R@5 « successeur accepté » 0,86 → 0,91.
* **Le reranker** améliore le rang 1 (0,618 → 0,684) et supprime presque tous les faux refus (8 → 1, via le seuil `RR_MIN`) ; coût : ≈ 0,9 s ; il dégrade quelques questions lexicales.
* Poids de la fusion (`W_RERANK = 3,0`, 20 candidats) choisis sur le dev v2 (meilleur MRR ; à égalité on garde le plus prudent).
* Essais négatifs conservés : expansion de requête par pseudo-retour de pertinence (phase 1) ; première version de l'insertion des textes modificateurs par cosinus (faux positifs sur les articles voisins) :
  remplacée par une preuve textuelle (« l'article N du règlement n° X est modifié… »).

## 7. Qualité juridique et temporelle

Principe : ne jamais présenter la valeur d'un ancien texte quand un texte postérieur l'a modifiée (exemple critique : plafond 600 000 DA → 2 000 000 DA).
Sans date, la version applicable aujourd'hui ; avec une date, la version historique.

* **Date de référence** (`parse_as_of`) : « en 1998 », « en avril 1997 », « au 1er septembre 2016 », « avant 2018 ». Les textes postérieurs sont écartés/rétrogradés (`FUTURE_FACTOR` 0,15),
  les textes abrogés avant la date aussi (`ABROGATED_FACTOR` 0,30).
* **Preuve textuelle de modification** (`_TARGET_RE`, `amended_targets`, `supersedes`) : un passage est une version plus ancienne d'un autre seulement si le texte le dit (article visé) ou si deux modifications visent le même article ;
  un remplacement de texte entier exige un cosinus ≥ 0,95. Les voisins sémantiques ne sont plus confondus avec des versions (cause de faux positifs mesurés).
* **Textes modificateurs** remontés juste au-dessus du passage d'origine (`add_modifiers`) ; **chaîne de versions** pour « successivement / au cours de / évolution » (`expand_chain`) ;
  `resolve_versions` rétrograde la version remplacée (`VERSION_FACTOR` 0,60), sauf si son année est citée dans la question.
* **Côté LLM** : les passages remplacés ne sont **pas donnés** au modèle (mesuré : sinon il répondait 2 % au lieu de 1 % pour le taux actuel des réserves) ; la liste des textes modificateurs
  est bornée (les 4 plus récents) et écrite une fois par texte (avant : 4 080 jetons > contexte 4096 → erreur HTTP 400) ; consignes ajoutées au message utilisateur (le texte système est inchangé) pour les questions historiques,
  « valeur actuelle = source la plus récente » et « plusieurs textes ».
* **Clarification** : « Quel est le taux ? », « Quel est le délai applicable ? » demandent une précision (lexique de mots d'attribut + qualificatifs) : 8/8.
* Métadonnées utilisées : type, numéro, date, article, langue, statut (« STATUT À VÉRIFIER » sauf 2 abrogations prouvées en FR, 1 en AR), relations (modifie / complète / abroge / remplace et inverses).
  Dates de publication/entrée en vigueur : la date de signature est celle du texte ; la date d'entrée en vigueur n'est pas structurée dans le corpus (limite).

## 8. Génération (sans fine-tuning)

* Refus exact et JSON strict (les deux défauts de la phase 1) : décodage contraint par schéma JSON (`response_format json_schema`, repli `json_object`), règle 3 bis du prompt, normalisation
  « non précisé + found=true → refus ». Jeu aveugle 40 items : 38/40 → 39/40 ; reste B021 (instruction générique « tableau JSON de chaînes », hors chemin de l'agent).
* Robustesse : une requête refusée par le serveur (HTTP 400) ou interrompue bascule en réponse extractive avec une note au lieu de planter ; un refus du modèle conserve sa latence et la liste des passages donnés.
* Interface : « Sources retrouvées » (Document, Article, Date, Statut, Score + similarité, Source PDF / page) s'affichent **avant** « Réponse générée » ; l'extractif ne duplique pas les passages.

## 9. Performance (machine : i7-13700, 24 threads, 15,6 Go de RAM, sans GPU ; mesurée avec le LLM chargé et le crawl de fond actif)

| Mesure | Valeur |
|---|---|
| Latence recherche, legacy | 2,7 ms (moy.), p95 6,8 ms |
| Latence recherche, hybride | 9,0 ms (moy.), p95 14,8 ms (embedding question 4,6 ms) |
| Latence recherche, hybride + reranker | 893 ms (moy., 40 questions) ; 1 039 ms sur les 136 questions ; médiane 832 ms, p95 1,39 s ; dont reranking ≈ 864 ms pour 20 passages (mesuré 0,5–0,6 s sur une machine moins chargée) |
| Génération Qwen3-4B | ≈ 14 tok/s ; 27–36 s par réponse rédigée (médiane 26,6 s sur gold_v2) ; refus et clarifications sans appel LLM |
| RAM de l'agent | 167 Mo (corpus) → 987 Mo (+ embedder et vecteurs) → 1,67 Go (+ reranker) |
| RAM llama-server | 3,0 Go |
| RAM libre avec tout chargé | ≈ 3,0 Go (sur 15,6 Go, navigateur et messagerie ouverts) |
| Disque | modèles 0,62 Go ; index 0,05 Go ; Qwen 3,1 Go ; instantané 38 Mo |
| Vecteurs, mise à jour | cache incrémental par empreinte du texte : 8 chunks encodés sur 10 817 en 1,8 s (contre 5,6 min en entier) ; vecteurs inchangés bit à bit |

## 10. Corpus (instantané figé `D:\llm\snapshots\corpus_2026-10-06`)

* FR : 754 documents (640 textes), 7 785 chunks (médiane 350 caractères ; articles 5 829, annexes 561, préambules 618, corps entier 777) ; 361 instructions, 223 règlements, 155 notes, 8 lignes directrices, 4 lois, 3 ordonnances ; 1990-03 → 2026-08.
* AR : 318 documents, 3 029 chunks, dont **2 217 issus de l'OCR** (73 %) ; 1 document de langue indéterminée.
* Statuts : 752/754 « STATUT À VÉRIFIER » (FR), 2 abrogés prouvés. Relations FR : 163 documents modifient un autre, 106 complètent, 108 abrogent, 34 remplacent.
* Anomalies connues : 114 copies multiples (`~N`) listées mais non départagées, 3 documents sans date, 2 sans numéro, 982 chunks FR « à vérifier » (189 OCR), 2 783 chunks AR à vérifier ; la numérotation d'articles arabes est parfois dégradée par l'OCR.
* **Reconstruction en cours** : un nouveau crawl du site (≈ 1 000/1 665 pages au moment de la rédaction) enchaîne scope → téléchargement → build. À sa fin, lancer `python -m boa_pipeline vectors`
  (incrémental). Les mesures de ce document portent sur l'instantané figé, pas sur le corpus reconstruit.

## 11. Fine-tuning : décision

**Non nécessaire aujourd'hui, et aucun calcul n'a été lancé.** Sur 112 questions, les échecs du moteur final sont d'abord liés au retrieval et au corpus ; les échecs purement génératifs
(liste incomplète, refus à tort, réponse hésitante : X028, X021, V010, V011, X024, X029) sont ≈ 6 questions sur 112, ce qui ne justifie pas un entraînement. Les deux défauts de la phase 1 sont traités sans fine-tuning (§8).
Si, après les actions P0/P1 et sur un jeu validé par un juriste, plus de ≈ 15 % des questions répondables ont le bon passage mais une mauvaise réponse, préparer :
format JSONL chat (système + question + sources + JSON `{found, answer, citations}`), 500–1 500 exemples validés humainement (dont ≥ 25 % de refus, clarifications et questions historiques),
séparation par texte (pas par question), **aucune donnée générée par Claude** (conditions d'utilisation), entraînement sur GPU externe uniquement avec **autorisation explicite** (le corpus doit rester local).
Un fine-tuning du modèle d'embeddings sur des paires validées serait plus prometteur que celui du LLM.

## 12. Prochaines étapes

**P0**
1. Faire rédiger et valider par un juriste un jeu aveugle de 100–150 questions (v6) et le mesurer **une seule fois** avec le protocole ci-dessus (les chiffres actuels ne sont pas aveugles).
2. Fin du crawl → build → `python -m boa_pipeline vectors` ; relancer les tests ; vérifier que l'agent par défaut (`auto`) n'est pas en repli.
3. Séries annuelles sans relation (prime de garantie des dépôts : 23 instructions) : déduire « la plus récente » d'une série à intitulé identique.
4. Valider avec un juriste la liste des « source différente mais pertinente » (W005, X008, X009, V039) et le gold discutable (X008, X019, X021).

**P1**
5. Poids de fusion et reranker sur ≥ 150 questions de développement validées (le moteur final perd sur les questions lexicales : pondération selon la rareté des termes).
6. Quantifier l'embedder en int8 (≈ −500 Mo de RAM) ; ne reranker que si l'écart entre les deux premiers est faible (−0,5 s en moyenne).
7. Réponses « plusieurs textes » composées sans LLM (énumération des textes modificateurs trouvés) ; réponse en arabe pour une question arabe.
8. Qualité de l'OCR arabe (re-OCR ciblé) : l'arabe est limité par le texte source.

**P2**
9. Modèle plus grand (Qwen3-8B Q4, ≈ 5 Go, ≈ 7 tok/s) à comparer sur le jeu v6 ; fine-tuning d'embeddings ; fine-tuning LLM seulement si les critères du §11 sont remplis et avec autorisation explicite.

## 13. Journal des modifications

* Ajoutés : `agent_fr/retrieve2.py`, `embed.py`, `rerank.py`, `build_vectors.py`, `pipelines.py` ; `agent_fr/eval/` : `retrieval_eval.py`, `e2e_eval.py`, `adjudicate.py`, `perf_bench.py`, `make_tables.py`, `build_gold_v3.py`, `build_gold_v4.py`, `build_gold_v5.py`, jeux et résultats ;
  `docs/RETRIEVAL_PHASE2.md`, `docs/tables_phase2.md` ; stage `vectors` dans `boa_pipeline`.
* Modifiés : `retrieve.py` (expose `resolve_references`, `clarify`, `timings`, `superseded_by`), `agent.py` (choix du moteur, repli), `answer.py` (relations bornées, garde-fou de taille, consignes, versions remplacées écartées, refus avec latence),
  `llm_backends.py` (profil local `max_chars`), `app.py` (deux blocs), `index.py` (instantané), `tests/` (21 tests agent, 7 pipeline : tous passent).
* **Rien supprimé** : ancien moteur, corpus, tests, sauvegardes de chaque version de `retrieve2.py` dans `D:\llm\snapshots\`.
* Retour arrière immédiat : `AGENT_RETRIEVER=legacy`. Repli automatique : modèles ou vecteurs absents → ancien moteur, avec une note dans la réponse.

## 14. Reproduire

```bash
python tests/test_agent.py ; python tests/test_pipeline.py
python -m agent_fr.build_vectors                        # vecteurs (incrémental ; AGENT_CORPUS_DIR pour l'instantané)
python -m agent_fr.eval.retrieval_eval --pipeline hybrid_rerank --tag all_hybrid_rerank --sets v2,v3,v4,v5
python -u -m agent_fr.eval.e2e_eval --pipeline hybrid_rerank --sets v3,v4,v5 --tag e2e_hybrid_rerank_v345     # serveur llama local démarré
python -m agent_fr.eval.adjudicate ; python -m agent_fr.eval.perf_bench ; python -m agent_fr.eval.make_tables > docs/tables_phase2.md
```
