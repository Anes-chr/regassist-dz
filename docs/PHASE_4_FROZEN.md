# PHASE_4_FROZEN — état gelé pour la validation juridique

**Statut de décision : NO-GO PROVISOIRE.** Raisons : validation humaine absente ; TEST v2 absent. Le gel n'est pas un jugement de qualité : il fige un état pour qu'un juriste réponde à une seule question —
*cette réponse est-elle juridiquement correcte et correctement sourcée ?* — sur un système qui ne bouge pas. Les problèmes techniques ayant diminué ne transforment pas ce statut en GO.

Marqueur : `PHASE_4_FROZEN` (racine du projet) ; manifeste : `agent_fr/eval/human/PHASE_4_FROZEN.manifest.json` (SHA-256 `177fbf82f6bfe03fb23c67adf649e87689d07f519377b52b0f55bcef94ee9c36`), créé le 2026-10-07T10:21:24.
Vérifier à tout moment : `python -m agent_fr.eval.human.freeze_phase4 verify` (code de sortie 1 au moindre écart ; un fichier de code ajouté sans être listé est aussi un écart).

## 1. Ce qui est gelé

| Élément | Valeur gelée |
|---|---|
| Versions | Python 3.14.4 ; Windows-10-10.0.19045-SP0 ; Tesseract `tesseract v5.5.0.20241111` ; llama.cpp `b11411` (`version: 0.5.0-dev (build 11411, commit 210791069)`) ; numpy 2.5.2 ; onnxruntime 1.30.0 ; tokenizers 0.23.2 ; requests 2.34.2 ; PyMuPDF 1.28.0 ; pytesseract 0.3.13 ; Pillow 12.2.0 ; psutil 7.2.2 ; truststore 0.10.4 ; Flask 3.1.3 ; python-docx 1.2.0 ; openpyxl 3.1.5 |
| Configuration du retrieval | TOPN = 60, COS_MIN = 0.855, COS_HIGH = 0.88, RR_MIN = -1.9, MIN_COV = 0.3, MIN_RATIO = 0.12, SUPERSEDED_FACTOR = 0.92, FUTURE_FACTOR = 0.15, ABROGATED_FACTOR = 0.3, VERSION_FACTOR = 0.6, SERIES_MATCH = 1.0, SERIES_OTHER = 0.4, PAIR_COS_WHOLE = 0.95, RERANK_N = 20, RRF_K = 60, W_BM25 = 1.0, W_RERANK = 3.0, W_VEC = 1.0 ; moteur par défaut : `hybrid_rerank` (`AGENT_RETRIEVER=auto`, repli automatique sur `legacy`, `AGENT_RETRIEVER=legacy` = retour arrière) ; moteurs enregistrés : bm25, hybrid, hybrid_plain, hybrid_rerank, legacy, vector |
| Configuration du LLM | fournisseur par défaut **local** (l'API distante exige `AGENT_LLM=anthropic` **et** `AGENT_ALLOW_REMOTE_LLM=1`) ; profil local {"k": 4, "excerpt": 1000, "max_tokens": 600, "max_chars": 6400} ; sortie JSON contrainte par schéma ; serveur `llama-server` sur 127.0.0.1:8187 (arguments et paramètres : `llm_local/start_server.ps1`, `config.ps1`, empreintes dans le manifeste) ; empreinte du prompt système `fcf03ca71735…` |
| Chunking et OCR | CHUNK_MAX_CHARS = 2400, OCR_DPI = 300, OCR_DPI_AR = 400, OCR_MIN_CHARS_PER_PAGE = 40, OCR_LOW_CONF = 75.0 ; OCR actuel : Tesseract 5.5, modèle ara (rapide, installé) + fra, 400 dpi pour l'arabe, repli OCR des couches texte corrompues ; `tessdata_best` : **D:/llm/tessdata_best (ara best) : NON DÉPLOYÉ** ; `OCR_UNCERTAIN` : **actif (boa_pipeline/ocr_check.py -> chunks -> agent_fr/answer.py ocr_warnings)** (80 chunks marqués dans l'instantané) |
| Modèles (SHA-256) | qwen3-4b-instruct-2507-q4_k_m.gguf `3605803b982c…` (2381 Mo) ; llama-server.exe `6e3775be4aee…` (0 Mo) ; model.onnx `ca456c06b3a9…` (448 Mo) ; embeddings/multilingual-e5-small/tokenizer.json `0b44a9d7b51c…` (16 Mo) ; model_quint8_avx2.onnx `6c2513767fb6…` (113 Mo) ; rerankers/mmarco-mMiniLMv2-L12-H384/tokenizer.json `62c24cdc13d4…` (16 Mo) ; ara.traineddata `ab9d157d8e38…` (12 Mo) ; fra.traineddata `ced037562e8c…` (1 Mo) |
| Embeddings | `intfloat/multilingual-e5-small` (ONNX, CPU) — fichiers `model.onnx` et `tokenizer.json` ci-dessus |
| Reranker | `mmarco-mMiniLMv2-L12-H384` int8 (`model_quint8_avx2.onnx`) — ci-dessus |
| Corpus (instantané `D:/llm/snapshots/corpus_phase4`) | chunks_ar.jsonl `fcd0de8cb442…` ; chunks_fr.jsonl `1be96c57aa72…` ; chunks_und.jsonl `c04d754e7924…` ; documents_ar.json `2b35d72a565e…` ; documents_fr.json `5efc64ae4546…` ; documents_und.json `0cbd46ba77d1…` ; legal_status.json `1a6656fb328d…` ; 1085 documents ; corpus vivant identique à l'instantané ; 1085 PDF sources, empreinte agrégée `80fd4c0b7aa1…`, aucun écart avec `file_hash` |
| Entrées du pipeline | `state/candidates.json`, `state.json`, `media_index.json`, `pages.json`, cache d'extraction (OCR) : 1320 fichiers, empreinte agrégée `2f94342736ba…` |
| Index (vecteurs) | `vec_df4dd33e8c3b.npy` `31f4edbf5268…` ; `vec_4da0cd6ae37e.npy` `31f4edbf5268…` (11 314 vecteurs, dimension 384 ; le cache `vec_cache_e5small.npz` est volatil, noté à titre informatif) |
| TEST v1 | 11 fichiers (`frozen_test_v1.sha256.json`) : benchmark_v1_draft.jsonl `f56d576d4e79…` ; human_bench_test_final.json `3c9b28f00824…` ; human_score_test_final.json `726f0443f79b…` |
| Règles de notation et de décision | bench.py `6803102a430a…` ; decision_criteria.md `50c804e43720…` ; run_bench.py `b8c5a88c4a33…` ; score.py `af6c6fb981a5…` |
| Code pertinent | 94 fichiers (`agent_fr/`, `boa_pipeline/`, `tests/`, `llm_local/`), empreinte agrégée `9d3f8d739605a01dd7f4a6127f79011e6a4d8b4bd9fbd16b2db64d63a7b27011` |
| Interfaces de relecture et fiches | 10 fichiers de `review/` : benchmark_review_p4.html `4c1e0af666c8…` ; human_eval_p4.html `047523cdb544…` |
| Résultats de la phase 4 | 80 fichiers (sorties DEV, régression, OCR, intégrité), empreinte agrégée `98f85bae112c80bf…` |

Les empreintes complètes sont dans le manifeste ; ce tableau en donne les 12 premiers caractères.

## 2. Reproductibilité vérifiée (`freeze_phase4 repro`, sans rien modifier)

| Contrôle | Résultat |
|---|---|
| Empreintes | identiques à l’état gelé |
| Vecteurs ré-encodés **en entier** (11314 chunks) | cosinus minimal 1.0, moyen 1.0, 0 vecteur(s) < 0,99999 : l'index est reproductible |
| Corpus reconstruit depuis les PDF sources + `state/` dans un dossier temporaire (le corpus vivant n'est pas touché) | fichiers de chunks **identiques octet pour octet** (chunks_fr.jsonl, chunks_ar.jsonl, chunks_und.jsonl) ; documents identiques (contenu JSON) |
| Retrieval DEV rejoué (`hybrid_rerank`) | 78 / 78 classements identiques aux sorties enregistrées |
| Génération LLM rejouée sans cache | 6 / 6 réponses identiques mot pour mot (petit échantillon ; les sorties enregistrées restent la référence) |

Un premier essai (`phase4_reproducibility_run1_llm_indisponible.json`) a échoué sur le seul contrôle LLM parce que `llama-server` était arrêté (le replay est devenu extractif) ; le serveur a été relancé par `llm_local/start_server.ps1`, sans modification, et le contrôle a été refait. TEST v1 n'est jamais ré-exécuté par ces contrôles.

## 3. Ce qui est interdit et ce qui reste permis

**Interdit** (tout écart est détecté par `verify`) : modifier les embeddings, le reranker, les poids de fusion, le chunking, les règles de ranking, la logique temporelle, les seuils, la notation, TEST v1 ; déployer `tessdata_best` ; corriger H120 ou H129 spécifiquement ; créer des questions de TEST v2 ; lancer une nouvelle optimisation.

**Permis** sans toucher au système : documentation, sauvegarde, vérification d'intégrité, export de résultats, préparation des interfaces et des rapports, préparation du corpus pour le juriste, vérification des empreintes, vérification de reproductibilité.

## 4. Cas connus, laissés tels quels

* **H120** : refus à tort en phase 3, réponse hors sujet en phase 4 — [CAS_CRITIQUES_A_EXAMINER.md](CAS_CRITIQUES_A_EXAMINER.md).
* **H129** : valeur périmée présentée comme actuelle ; la notation automatique ne la compte pas comme erreur critique — idem.
* **OCR arabe** : « % » lu comme des chiffres (902.75) ; `tessdata_best` ne le corrige pas (non déployé) ; `OCR_UNCERTAIN` actif.
* **Trois conflits de dates FR/AR** (REG-90-01, REG-02-01, REG-06-01) — [ARBITRAGE_JUMEAUX_FR_AR.md](ARBITRAGE_JUMEAUX_FR_AR.md) ; aucun choix automatique.
* Anomalies du contrôle d'intégrité conservées (A_CORRIGER) : 10 chunks à couche texte partiellement corrompue ; 2 faux positifs de dates (recueils) ; 20 documents sans date ; 16 références à des textes absents du corpus.

## 5. Historique du gel (transparence)

Le gel a été écrit une première fois (`PHASE_4_FROZEN.manifest.v0_superseded.json`, SHA-256 `c6c5689a388ad750190539596cf3ab92535cb7776adceefeb6f0c9748e4c7ab3`), puis **recréé** parce que le contrôle de reproductibilité du LLM de l'outil `freeze_phase4.py` confondait « serveur éteint » et « réponses différentes ». La comparaison des deux manifestes montre **un seul fichier de code différent : `agent_fr/eval/human/freeze_phase4.py`** ; corpus, index, configuration, versions, modèles, règles, TEST v1, benchmark, interfaces et résultats sont identiques.

## 6. Sauvegarde

`D:\llm\snapshots\phase4_frozen_backup\` : `code_etat_docs_corpus_derive.zip` (code, documentation, `state/` avec le cache d'OCR, corpus dérivé, manifeste, interfaces, résultats) et `corpus_raw_sources_pdf.zip` (les 1 085 PDF sources), avec `SHA256SUMS.txt` et `README.txt`. L'instantané du corpus, les vecteurs, les modèles, llama.cpp et `tessdata_best` restent sous `D:\llm` (empreintes dans le manifeste).

## 7. Sortie du gel

Le gel ne se lève qu'après les réponses du juriste : (1) validation du benchmark et des 60 réponses, fiches H120 / H129 / conflits ; (2) recalcul séparé (hallucination juridique, factuelle, métadonnée interne ; notation automatique vs humaine) ; (3) TEST v2 rédigé indépendamment → validé → gelé (`test_v2.py freeze`, empreintes, verrou) → **une seule exécution** → résultats, **sans modification du moteur avant publication**. Seulement ensuite se décide, sur un benchmark validé, s'il faut corriger le corpus, le retrieval, le prompt, l'OCR, changer de modèle ou envisager un fine-tuning ; un nouveau gel porterait un autre nom (jamais une réécriture de celui-ci).
