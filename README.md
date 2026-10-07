# RegAssist DZ

**Projet éducatif non officiel.** Assistant d'exploration des textes réglementaires **publics** de la Banque d'Algérie (règlements, instructions, notes). Il n'est affilié ni à la Banque d'Algérie ni approuvé par elle.

* Il retrouve les passages pertinents dans les textes publiés sur le site de la Banque d'Algérie (recherche hybride lexicale + sémantique, reranker), puis un petit modèle de langage **local** rédige une réponse à partir de ces seuls passages, avec sources et liens vers les PDF officiels.
* **Tout est local** : aucun appel à un service distant, aucun modèle entraîné ou affiné sur ces textes.
* **Statut : NO-GO PROVISOIRE.** Les jeux d'évaluation ont été rédigés avec l'aide d'une IA et **n'ont pas été validés par un juriste** ; les réponses peuvent être incomplètes ou erronées et ne constituent pas un avis juridique. Seul le texte officiel (PDF) fait foi. Voir [docs/NOTE_AU_JURISTE.md](docs/NOTE_AU_JURISTE.md).
* Code et documentation produits avec l'assistance d'une IA (Claude).

## Contenu du dépôt

| Dossier | Rôle |
|---|---|
| `boa_pipeline/` | collecte, extraction (OCR), segmentation et relations juridiques du corpus |
| `agent_fr/` | agent : recherche, statut juridique, réponse ; évaluation (`eval/`) et outils du gel |
| `local_app/` | application locale (API Flask + interface web) et ses tests |
| `llm_local/` | démarrage du LLM local (llama.cpp) |
| `tests/` | tests du système |
| `docs/` | documentation (architecture, phases 2 à 4, gel `PHASE_4_FROZEN`, déploiement local, interface) |
| `start_local.ps1`, `stop_local.ps1` | démarrage et arrêt de l'application locale |

## Ce qui n'est PAS dans le dépôt

Les **données** : corpus (PDF sources et textes dérivés), état de collecte, modèles, index vectoriels, caches, sorties d'évaluation et jeux de relecture (qui contiennent des extraits des textes). Raisons : taille, et règle du projet de ne pas diffuser le contenu du corpus sans autorisation explicite. Le manifeste d'empreintes du gel (`agent_fr/eval/human/PHASE_4_FROZEN.manifest.json`) est inclus ; la vérification complète (`python -m agent_fr.eval.human.freeze_phase4 verify`) exige les données et ne passe donc que dans l'environnement d'origine.

## Utilisation (environnement d'origine : Windows 10, Python 3.14)

```powershell
pip install -r requirements.txt
.\start_local.ps1        # puis http://127.0.0.1:8790
.\stop_local.ps1
python local_app/tests/test_api.py
```

Détails, ports, sécurité, journaux et diagnostic : [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md) et [docs/LOCAL_UI.md](docs/LOCAL_UI.md). État gelé du système : [docs/PHASE_4_FROZEN.md](docs/PHASE_4_FROZEN.md).

## Licence

Aucune licence n'a été choisie : par défaut, tous droits réservés. Les textes de la Banque d'Algérie restent la propriété de leur auteur ; vérifier ses conditions de réutilisation avant toute diffusion de données.
