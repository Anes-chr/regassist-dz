# Architecture du pipeline — corpus juridique Banque d'Algérie

Source unique : `https://www.bank-of-algeria.dz/` (WordPress). Constats de l'exploration initiale :

* `robots.txt` : seuls `/wp-admin/` (sauf admin-ajax) et un JSON de plugin sont interdits. Sitemap : `/wp-sitemap.xml`
  (≈1 150 articles, 119 pages, 67 catégories).
* Les textes juridiques sont regroupés sous `/cadre-legislatif-et-reglementaire/` (règlements / instructions par thème,
  loi monétaire et bancaire, lignes directrices, notes aux banques) ; les PDF sont sous `/stoodroa/AAAA/MM/…`.
* L'API REST publique WordPress (`/wp-json/wp/v2/media`) liste ~4 300 PDF de la médiathèque (dont beaucoup de
  contenus statistiques). Elle sert **uniquement de contrôle d'exhaustivité** et de source de date de publication ;
  un PDF présent en médiathèque mais lié depuis aucune page publique n'est **pas** intégré (signalé dans
  `reports/unlinked_media.json`), car rien ne prouve qu'il est publié.

```
Crawler (sitemap + BFS, robots.txt, délai poli, cache conditionnel)         crawl.py
   ↓
URL discovery  → pages.json : titre, liens-documents + contexte (h1/h2, page source)
   ↓
Scope / classifier  (pages juridiques ← hub ; type/numéro/date/langue/catégorie)   scope.py classify.py
   ↓
Document downloader (HEAD/ETag/sha256, raw/ immuable, versions conservées)  download.py
   ↓
Extractor PDF/HTML/DOCX/XLSX  (PyMuPDF par page)                            extract.py
   ↓
OCR si page sans texte (Tesseract fra/ara, confiance par page)              extract.py
   ↓
Text cleaner (en-têtes/pieds répétés, n° de page, reflow prudent)           clean.py
   ↓
Legal structure parser (Titre/Chapitre/Section/Article/Annexe, FR + AR)     structure.py
   ↓
Metadata extractor + relations (modifie/abroge/complète/remplace)           relations.py
   ↓
Deduplication (hash fichier, hash texte normalisé, URL multiples)           dedup.py
   ↓
Version/link detection + statut (jamais inventé : « STATUT À VÉRIFIER »)    relations.py
   ↓
Bilingual pairing FR/AR (work_id commun, versions séparées)                 relations.py
   ↓
Chunking sémantique (1 article = 1 chunk, découpe par alinéa si trop long)  chunk.py
   ↓
Quality validation → reports/*.json                                         quality.py
   ↓
corpus/{documents,chunks,metadata,raw,extracted,reports}
   ↓  (étape ultérieure, non incluse)
Vector DB / RAG   → voir docs/RAG.md
```

## Principes
* **Source officielle d'abord** : aucun texte hors du domaine ; aucune information juridique ajoutée.
* **Incrémental** : `state/state.json` conserve ETag / Last-Modified / sha256 par URL ; un relancement ne retélécharge
  que ce qui a changé ; `reports/update_report.json` liste nouveaux / modifiés / disparus.
* **Raw immuable** : `raw/<sha12>__<nom>` ; une nouvelle version d'un fichier ne remplace pas l'ancienne.
* **Pas de correction silencieuse** : le texte est nettoyé (artefacts techniques) mais jamais reformulé ; l'OCR est
  marqué par page avec sa confiance ; tout document OCR va en revue humaine.
* **Statut juridique** : `abrogé` seulement si un texte du corpus l'abroge explicitement (preuve citée) ;
  sinon `STATUT À VÉRIFIER`.
