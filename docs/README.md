# Pipeline de corpus juridique — Banque d'Algérie

Construit un corpus **traçable, structuré et versionné** à partir des seules sources officielles de
`https://www.bank-of-algeria.dz/`, prêt pour un système RAG. Aucun entraînement de LLM n'est lancé.
Agent français : [AGENT.md](AGENT.md) · Recherche phase 2 : [RETRIEVAL_PHASE2.md](RETRIEVAL_PHASE2.md) · Architecture : [ARCHITECTURE.md](ARCHITECTURE.md) · RAG : [RAG.md](RAG.md) · Mises à jour : [UPDATE.md](UPDATE.md).

## Prérequis (Windows / Python ≥ 3.11)
```bash
pip install requests beautifulsoup4 lxml pymupdf pytesseract pillow python-docx openpyxl truststore
```
* **Tesseract OCR** avec les langues `fra` et `ara` (installé dans `C:\Program Files\Tesseract-OCR`).
* Recherche sémantique (phase 2, optionnelle ; l'agent retombe sur l'ancien moteur lexical si absente) :
  `pip install onnxruntime tokenizers numpy` + modèles locaux sous `D:\llm\models` (embeddings `multilingual-e5-small`, reranker `mmarco-mMiniLMv2` int8) ;
  vecteurs dans `D:\llm\index`. Rien n'est envoyé hors de la machine. Détails : [RETRIEVAL_PHASE2.md](RETRIEVAL_PHASE2.md).
* `truststore` : le serveur du site n'envoie pas son certificat intermédiaire ; on utilise le magasin de certificats
  Windows au lieu de désactiver la vérification TLS (jamais de `verify=False`).

## Lancer
```bash
python -m boa_pipeline all          # crawl → scope → download → build → status
# ou étape par étape :
python -m boa_pipeline crawl        # explore le site (sitemap + liens), cache HTML conditionnel
python -m boa_pipeline scope        # détermine les documents juridiques (state/candidates.json)
python -m boa_pipeline download     # télécharge/actualise les documents (raw/), index médiathèque
python -m boa_pipeline build        # extraction, OCR, structure, relations, chunks, rapports
python -m boa_pipeline status       # (phase 3) statut juridique de chaque texte / article, preuves à l'appui (legal_status.json)
python -m boa_pipeline vectors      # (phase 2) encode LOCALEMENT les chunks nouveaux/modifiés pour la recherche sémantique (cache incrémental)
```
Phase 4 : `python -m boa_pipeline.deadlinks_check` vérifie en ligne (HEAD polis) l'état des liens en échec listés dans `corpus/reports/dead_links.json` ; `boa_pipeline/twin_overrides.json` reçoit les appariements FR/AR **confirmés par un humain** ;
`python -m agent_fr.eval.human.corpus_check --corpus <instantané>` contrôle l'intégrité (identifiants de chunks, jumeaux, liens, `OCR_UNCERTAIN`, vecteurs).
Options : `--delay 1.0` (politesse), `--full` (ignorer les caches), `--max-pages N` (test).
Le crawl complet (~1 700 pages) est lent (~3 s/page) ; le périmètre juridique est exploré en priorité.

## Sorties (`corpus/`)
| Chemin | Contenu |
|---|---|
| `documents/<document_id>.json` | métadonnées + relations + arbre structurel + unités (articles) avec pages + qualité |
| `chunks/chunks.jsonl` | 1 ligne = 1 chunk (article ou alinéa) avec métadonnées de citation |
| `metadata/documents.json` | métadonnées de tous les documents (sans le texte) |
| `raw/` | fichiers originaux (`<sha12>__<nom>`), immuables ; `raw/html/` = cache des pages |
| `extracted/<document_id>.txt` | texte nettoyé avec marqueurs `[[PAGE n]]` |
| `reports/` | `crawl_report`, `extraction_report`, `duplicates`, `failed_documents`, `ocr_required`, `manual_review`, `download_report`, `unlinked_media` |

`state/` (hors corpus) : `pages.json` (index des pages), `candidates.json` (catalogue + hors-périmètre avec raisons),
`state.json` (hashes/ETag par URL), `media_index.json`, `extract_cache/`.

## Modèle de données (extrait)
* `work_id` = texte juridique (ex. `REG-2014-03`) ; `document_id` = version linguistique (`REG-2014-03.fr`, `.ar`).
  FR et AR d'un même texte partagent le `work_id` mais restent des documents **distincts** (`same_work_documents`).
* `status` : `abrogé` **uniquement** si l'intitulé d'un texte officiel du corpus l'abroge/remplace sans réserve
  (preuve dans `status_evidence`) ; sinon **`STATUT À VÉRIFIER`**. Le site ne publie aucun statut de vigueur.
* `abroge / modifie / complète / remplace` (+ `*_par`) : relations extraites de l'intitulé (preuve forte) et du texte
  (preuve à vérifier), avec citation et page ; références non résolues dans `unresolved_references`.
* `publication_date` = date de mise en ligne (métadonnée WordPress), **pas** la date de signature ni du JO.
* Chaque chunk : `source_url` (page du site), `document_url` (PDF), `page_number`, `article`, `chapter`, `section`,
  `status`, `extraction_method`, `needs_review`.

## Limites assumées
Voir `reports/crawl_report.json` et `reports/extraction_report.json` : le rapport indique ce qui est couvert et ce qui ne l'est
pas. Les PDF présents dans la médiathèque mais non liés depuis une page publique ne sont **pas** intégrés
(`unlinked_media.json`). L'OCR n'est jamais présumé fiable : tout document OCR figure dans `ocr_required.json`.
