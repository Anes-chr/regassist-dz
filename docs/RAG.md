# Ajouter le RAG au corpus (étape ultérieure)

Le corpus est prêt : `corpus/chunks/chunks.jsonl` (un chunk = un article ou un alinéa, avec contexte et citations).

## 1. Indexation
* Texte à **embedder** : `text_with_context` (en-tête document + hiérarchie + texte).
* Texte à **citer / afficher** : `text` (fidèle au document).
* Métadonnées à stocker avec chaque vecteur : tout le chunk sauf `text_with_context`.
* Modèle d'embedding **multilingue** (FR + AR). Index séparés ou filtre `language`.
* Base vectorielle au choix (Chroma, pgvector, Qdrant…). Exemple minimal :

```python
import json, chromadb
col = chromadb.PersistentClient("vdb").get_or_create_collection("boa")
rows = [json.loads(l) for l in open("corpus/chunks/chunks.jsonl", encoding="utf-8")]
col.add(ids=[r["chunk_id"] for r in rows],
        documents=[r["text_with_context"] for r in rows],
        metadatas=[{k: (v if v is not None else "") for k, v in r.items()
                    if k not in ("text", "text_with_context")} for r in rows])
```

## 2. Règles que l'assistant doit respecter (à mettre dans le prompt système)
1. Répondre **uniquement** à partir des chunks récupérés ; sinon répondre :
   « Je ne trouve pas de disposition correspondante dans le corpus disponible. »
2. Citer systématiquement : type, numéro, date du texte, **article**, page, et `document_url` / `source_url`.
3. Annoncer le champ `status` : s'il vaut `STATUT À VÉRIFIER`, ne **jamais** dire « en vigueur » ; si `modifié_par`
   est non vide, récupérer et citer aussi les textes modificateurs.
4. Questions « avant la modification » : utiliser les relations `modifie_par` / `remplace_par` des fichiers
   `documents/*.json` pour retrouver les deux versions (aucune n'a été supprimée).
5. Chunks `needs_review = true` ou `extraction_method = ocr` : signaler que le texte n'est pas vérifié.
6. Ne jamais présenter une interprétation comme un fait juridique ; ne pas inventer de numéro d'article.
7. FR et AR d'un même texte partagent le `work_id` : ne pas les traiter comme deux règles distinctes.

## 3. Recherche hybride recommandée
Vecteurs + BM25 (numéros d'articles, « n° 2014-03 » sont des requêtes lexicales) ; filtre par `work_id`,
`document_type`, `date` ; re-classement optionnel.

## 4. Fine-tuning (non lancé)
Aucun jeu question/réponse n'a été fabriqué. Si vous en créez un (`{"question","context","answer","sources"}`),
signalez explicitement qu'il est **synthétique** et faites-le relire par un juriste.
