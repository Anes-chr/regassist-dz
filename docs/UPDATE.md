# Mettre à jour le corpus sans tout retélécharger

```bash
python -m boa_pipeline all
```
Le relancement est incrémental :

| Niveau | Mécanisme |
|---|---|
| Pages HTML | requêtes conditionnelles (`ETag` / `Last-Modified`) ; sinon comparaison du hash du contenu ; un crawl relancé < 6 h après le précédent réutilise le cache (reprise après interruption) |
| Documents | `HEAD` + `ETag`/`Last-Modified`/taille ; si changé : retéléchargement, nouveau `sha256`. L'ancienne version reste dans `raw/` et dans `state.json › history` |
| Extraction/OCR | cache `state/extract_cache/<sha>_<lang>_v<version>.json` : un fichier inchangé n'est ni réextrait ni réOCRisé |
| Documents disparus du site | marqués `removed` dans `state.json` ; **jamais supprimés** du corpus |

Rapports de différences : `reports/download_report.json` → `new`, `changed`, `unchanged`, `failed`, `removed_from_site` ;
`reports/crawl_report.json` → `pages_changed_since_last_run`.

* Forcer un retéléchargement : `python -m boa_pipeline download --full`.
* Changer les règles d'extraction/structure : incrémenter `PIPELINE_VERSION` dans `boa_pipeline/build.py`
  (invalide le cache d'extraction), puis `python -m boa_pipeline build`.
* Un texte modifié par un nouveau texte : les deux restent dans le corpus ; la relation est recalculée à chaque `build`
  (`modifie_par`, `abroge_par`…).
