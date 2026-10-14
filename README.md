# RegAssist DZ

**Projet éducatif non officiel.** Assistant d'exploration des textes réglementaires **publics** de la Banque d'Algérie (règlements, instructions, notes). Il n'est ni affilié à la Banque d'Algérie ni approuvé par elle.

> **Statut du système : NO-GO PROVISOIRE.** Les jeux d'évaluation ont été rédigés avec l'aide d'une IA et **n'ont pas été validés par un juriste**. Les réponses peuvent être incomplètes ou erronées et ne constituent pas un avis juridique : **seul le texte officiel (PDF) fait foi**. Voir [docs/NOTE_AU_JURISTE.md](docs/NOTE_AU_JURISTE.md).

## En bref

* Il pose une question en français et retrouve les passages pertinents dans 1 085 documents officiels (recherche hybride lexicale + sémantique, puis reranker).
* Un petit modèle de langage **local** rédige une réponse à partir de ces seuls passages, avec l'article, la page et le lien vers le PDF officiel. S'il ne trouve rien, il le dit au lieu d'inventer.
* Il signale quand un texte a été modifié, remplacé ou abrogé, ou quand son statut est à vérifier.
* **Tout est local** : aucun service distant, aucune clé d'API, aucun modèle entraîné ou affiné sur ces textes.

```
question ──▶ application locale (Flask, 127.0.0.1:8790)
                │
                ▼
   recherche hybride (BM25 + embeddings e5-small + fusion RRF)
                │  logique juridique et temporelle (versions, abrogations)
                ▼
   reranker (mmarco, ONNX) ──▶ passages retenus
                │
                ▼
   LLM local (Qwen3-4B Q4_K_M, llama.cpp, CPU) ──▶ réponse + sources citées
```

## Résultats mesurés

| Mesure | Valeur | Remarque |
|---|---|---|
| La bonne source est dans les 5 premiers résultats (Recall@5), 136 questions historiques | 0,765 avec l'ancienne recherche, **0,890** en phase 2, **0,868** pour le système gelé (phase 4) | la mesure de la phase 4 n'est pas strictement comparable à celle de la phase 2 (corpus remappé) |
| Test à l'aveugle TEST v1, passé une seule fois (42 questions à réponse attendue sur 52) | **52,4 %** de réponses correctes, **14,3 %** d'hallucinations (6/42) | notation **automatique** ; le seuil de NO-GO est > 10 % d'hallucinations : d'où le **NO-GO provisoire** |

Ces questions ont été écrites avec l'aide d'une IA et notées automatiquement : elles ne remplacent pas une validation juridique humaine. Un second test indépendant (TEST v2) devra être rédigé par un juriste. Détails : [docs/PHASE_4_FROZEN.md](docs/PHASE_4_FROZEN.md), [docs/RETRIEVAL_PHASE3.md](docs/RETRIEVAL_PHASE3.md) et [docs/RETRIEVAL_PHASE4.md](docs/RETRIEVAL_PHASE4.md).

## Démarrage rapide

**Sur la machine d'origine** (Windows 10, Python 3.14, modèles dans `D:\llm`) :

```powershell
pip install -r requirements.txt
.\start_local.ps1          # puis http://127.0.0.1:8790
.\stop_local.ps1           # arrêt
```

**Pour que des collègues l'utilisent depuis leur navigateur** (option, désactivée par défaut) : `.\start_local.ps1 -Lan` ouvre l'accès sur le réseau local avec un code d'accès (affiché une seule fois). L'application tourne sur votre machine ; les autres ne font qu'afficher la page. À n'activer qu'avec l'accord de la sécurité informatique si la machine appartient à une organisation. Garde-fous et limites : [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md) § 15. Pour que le service reste allumé et redémarre seul après un plantage : `.\autostart.ps1 -Install -Lan -NoCode` (§ 17).

**Sur une autre machine** : le dépôt contient le corpus et les données de gel ; les modèles sont téléchargés et vérifiés par un script.

```powershell
git config --global core.longpaths true
git clone https://github.com/SalimMabed/regassist-dz.git ; cd regassist-dz
pip install -r requirements.txt
.\replication\setup_machine.ps1        # modèles (~3 Go), vecteurs, instantané ; empreintes SHA-256 vérifiées
.\start_local.ps1
```

Prérequis, vérifications et limites : [docs/REPLICATION.md](docs/REPLICATION.md). Déploiement local, ports, journaux, diagnostic : [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md).

## Contenu du dépôt

| Élément | Rôle |
|---|---|
| `corpus/` | **corpus officiel** : PDF et pages HTML sources, textes extraits, chunks, métadonnées, rapports |
| `state/` | état de collecte (pages, candidats, cache d'extraction) |
| `boa_pipeline/` | collecte, extraction (OCR), segmentation et relations juridiques entre textes |
| `agent_fr/` | agent : recherche, statut juridique, réponse ; évaluation (`eval/`), jeux et résultats figés, outils du gel |
| `local_app/` | application locale (API Flask + interface web) et ses tests |
| `llm_local/` | démarrage du LLM local (llama.cpp) et mesures |
| `replication/` | script d'installation d'une autre machine, vecteurs d'embeddings et instantané du corpus |
| `tests/` | tests du système |
| `docs/` | documentation |
| `PHASE_4_FROZEN` | marqueur du gel ; le manifeste d'empreintes est `agent_fr/eval/human/PHASE_4_FROZEN.manifest.json` |
| `start_local.ps1`, `stop_local.ps1` | démarrage et arrêt de l'application locale (`-Lan` : accès réseau avec code) |
| `lan_firewall.ps1` | règle étroite du pare-feu Windows pour l'accès réseau (facultatif) |
| `autostart.ps1`, `keep_running.ps1` | tâche planifiée et superviseur qui gardent le service allumé et le relancent s'il tombe |

**Hors dépôt** : les modèles (trop gros pour Git, téléchargés par `replication/setup_machine.ps1`), les caches et les journaux d'exécution.

## Le gel `PHASE_4_FROZEN`

Le moteur, les embeddings, le reranker, les poids de fusion, le chunking et les jeux de test sont **figés** pour qu'un juriste valide un système qui ne bouge pas. Aucune amélioration n'est faite tant qu'il n'a pas répondu. La commande suivante doit toujours répondre « aucun écart » :

```powershell
python -m agent_fr.eval.human.freeze_phase4 verify
```

L'application locale (`local_app/`) n'est qu'une couche d'accès : elle appelle le moteur gelé tel quel.

## Tests

```powershell
python local_app/tests/test_api.py          # API, avec un faux agent (sans modèle)
python local_app/tests/test_smalltalk.py    # messages de courtoisie (« Bonjour », « Merci », « Qui es-tu ? »)
python local_app/tests/test_lan.py          # accès réseau optionnel : code d'accès, sessions, blocage, liaisons
python local_app/tests/test_ui.py           # interface dans Edge/Chrome sans fenêtre (Node >= 22)
python local_app/tests/test_integration.py  # chaîne réelle de bout en bout (application démarrée)
python tests/test_phase5_freeze.py          # tests du système : un script par thème (tests/test_*.py : agent, pipeline, statut juridique, OCR, gel…)
```

## Documentation

| Sujet | Document |
|---|---|
| Vue d'ensemble, architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AGENT.md](docs/AGENT.md), [docs/RAG.md](docs/RAG.md) |
| Recherche (phases 2 à 4) | [docs/RETRIEVAL_PHASE2.md](docs/RETRIEVAL_PHASE2.md), [docs/RETRIEVAL_PHASE3.md](docs/RETRIEVAL_PHASE3.md), [docs/RETRIEVAL_PHASE4.md](docs/RETRIEVAL_PHASE4.md) |
| Gel et statut | [docs/PHASE_4_FROZEN.md](docs/PHASE_4_FROZEN.md) |
| Relecture par un juriste | [docs/NOTE_AU_JURISTE.md](docs/NOTE_AU_JURISTE.md), [docs/HUMAN_REVIEW.md](docs/HUMAN_REVIEW.md), [docs/HUMAN_REVIEW_QUICKSTART.md](docs/HUMAN_REVIEW_QUICKSTART.md), [docs/CAS_CRITIQUES_A_EXAMINER.md](docs/CAS_CRITIQUES_A_EXAMINER.md) |
| Application locale | [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md), [docs/LOCAL_UI.md](docs/LOCAL_UI.md) |
| Autre machine | [docs/REPLICATION.md](docs/REPLICATION.md) |
| Mise à jour du corpus | [docs/UPDATE.md](docs/UPDATE.md) |
| LLM local | [llm_local/README.md](llm_local/README.md) |

## Limites connues

* Pas de validation juridique humaine : le statut reste NO-GO provisoire.
* Une seule question à la fois ; pas de mémoire de conversation.
* La recherche peut manquer un passage (par exemple un montant) pour les questions très larges, et une question qui touche plusieurs régimes n'est pas détectée comme ambiguë.
* Les réponses du LLM local sont plafonnées en longueur et peuvent être tronquées.
* Le statut juridique affiché peut être inexact (par exemple une abrogation implicite non détectée) : toujours vérifier sur le texte officiel.
* Arabe : l'OCR des scans doit encore être amélioré (les valeurs numériques incertaines sont signalées, jamais corrigées en silence).
* Interface testée sous Edge et Chrome seulement.

## Sécurité et confidentialité

Par défaut, l'application écoute uniquement sur `127.0.0.1` (l'accès réseau `-Lan` est une option explicite, protégée par un code), n'émet aucune requête sortante (hors clic de l'utilisateur sur un lien vers un PDF officiel), n'utilise aucune API distante et ne journalise pas le texte des questions par défaut. Voir [docs/LOCAL_DEPLOYMENT.md](docs/LOCAL_DEPLOYMENT.md) § 8.

## Licence, données et responsabilité

Aucune licence n'a été choisie : par défaut, tous droits réservés. Les textes de la Banque d'Algérie restent la propriété de leur auteur. Ce dépôt est **privé** et contient une copie de textes publics à des fins de reproductibilité : vérifiez leurs conditions de réutilisation **avant** de rendre le dépôt public ou de redistribuer le corpus.

Projet personnel, réalisé seul à partir de documents publics uniquement. Code et documentation produits avec l'assistance d'une IA (Claude). Ce projet n'est pas un conseil juridique.
