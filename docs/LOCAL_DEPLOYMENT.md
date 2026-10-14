# Déploiement local — assistant juridique (phase 6)

**Statut du système : NO-GO PROVISOIRE** (état `PHASE_4_FROZEN` : validation humaine absente, TEST v2 absent). Cette phase n'ajoute **qu'une couche d'accès** (API locale + interface web + scripts) : elle n'améliore ni ne corrige rien dans le système gelé et ne conclut rien sur sa fiabilité juridique. Voir [PHASE_4_FROZEN.md](PHASE_4_FROZEN.md) et [LOCAL_UI.md](LOCAL_UI.md).

```
.\start_local.ps1        puis        http://127.0.0.1:8790
```

## 1. Principe

Le système gelé est **utilisé en lecture seule** : l'application appelle `agent_fr.agent.ask(question, use_llm=True)` exactement comme l'ancienne interface Flask (`agent_fr/app.py`, port 8765, conservée et inchangée). Aucun fichier du moteur, du corpus, de l'index, des modèles, de l'OCR, des règles ni de TEST v1 n'est modifié ; tout le code nouveau vit hors des dossiers contrôlés par le gel (`local_app/`, `start_local.ps1`, `stop_local.ps1`), si bien que `python -m agent_fr.eval.human.freeze_phase4 verify` reste vert **sans toucher à son mécanisme**.

## 2. Architecture

```
Navigateur ──HTTP──▶ local_app (Flask, 127.0.0.1:8790)  ── sert l'interface statique ET l'API (même origine)
                          │  POST /api/chat
                          ▼
                    agent_fr.agent.ask(question, use_llm=True)        ← système gelé, appelé tel quel
                          │  recherche hybride BM25 + e5-small + RRF → logique juridique/temporelle → reranker → contexte
                          ▼
                    llama-server (127.0.0.1:8187, Qwen3-4B Q4_K_M, CPU)   ← llm_local\start_server.ps1
                          ▼
                    réponse + sources  ──▶ mise en forme (retrait des champs internes, notes assainies, durées) ──▶ navigateur
```

| Élément | Choix | Raison |
|---|---|---|
| API | Flask 3.1.3 (déjà installé et déjà dans le manifeste du gel) | FastAPI/uvicorn ne sont pas installés : ajouter des dépendances n'apportait rien |
| Frontend | HTML/CSS/JS purs, sans build ni Node à l'exécution | simplicité et stabilité ; fonctionne hors ligne |
| Processus | **un seul** serveur pour l'API et l'interface | une seule origine : aucune requête inter-sites, donc **aucun en-tête CORS** ; un processus de moins à superviser |
| Serveur HTTP | serveur WSGI de Werkzeug, multi-fil, lié à 127.0.0.1, sans partage de port (`SO_EXCLUSIVEADDRUSE`) | l'application est mono-utilisateur |
| Une question à la fois | verrou : une seconde reçoit HTTP 429 | le LLM local n'a qu'un emplacement (`-np 1`) et le CPU est partagé ; `/api/health` et `/api/status` répondent pendant ce temps |

### Ports

| Port | Usage | Remarque |
|---|---|---|
| **8790** | application (interface + API) | choisi libre ; changer par `-Port` |
| 8187 | llama-server | inchangé (`llm_local\config.ps1`), 127.0.0.1 uniquement |
| 8765 | ancienne interface Flask (`python -m agent_fr --serve`) | inchangée, indépendante |
| 3000, 8000 | **occupés** par Grafana et IncrediBuild (ils écoutent sur toutes les interfaces) | ports de l'exemple de cahier des charges non utilisés ; `start_local.ps1 -Port 3000` refuse de démarrer |

## 3. Prérequis

Aucune installation : tout est déjà en place pour le système gelé.

* Windows 10, PowerShell 5.1, Python 3.14 avec les paquets du gel (Flask, numpy, onnxruntime, tokenizers, requests). **Aucun paquet n'est ajouté.**
* Modèles et données du gel : `D:\llm\models` (e5-small, reranker, Qwen), `D:\llm\llama.cpp\b11411`, `D:\llm\index` (vecteurs), `corpus\`. `start_local.ps1` vérifie leur présence et nomme ce qui manque.
* Pour **lancer les tests** seulement : Node ≥ 22 et Edge ou Chrome (pour l'interface), `psutil` (intégration, déjà installé).

## 4. Démarrage

```powershell
.\start_local.ps1                 # [-Port 8790] [-SkipLlm] [-TimeoutSec 300]
```

Si PowerShell refuse d'exécuter le script : `powershell -ExecutionPolicy Bypass -File .\start_local.ps1`.

Le script, dans l'ordre :

1. vérifie Python, les fichiers requis, l'absence de variables d'environnement qui modifieraient le moteur gelé (liste § 6) ;
2. refuse de démarrer si l'application tourne déjà (`local_app\runtime\pids.json`) ou si le port est occupé (il nomme le programme, ne l'arrête jamais) ;
3. **llama-server** : s'il répond déjà sur 127.0.0.1:8187, il est réutilisé ; s'il est lancé mais muet, il attend (60 s) sans en créer un second ; s'il est absent, il appelle **`llm_local\start_server.ps1`** (aucun mécanisme concurrent) et enregistre son PID ;
4. démarre `python -m local_app` en arrière-plan (fenêtre cachée), journaux dans `local_app\runtime\` ;
5. attend que l'application soit prête : au démarrage elle rejoue une question de contrôle dans le moteur (encodeur, recherche, reranker ; **sans LLM**), ce qui prend quelques secondes ;
6. affiche un bilan **lu dans `/api/status`** (contrôles réels) :

```
RegAssist DZ - assistant juridique LOCAL
LLM local    OK   (qwen3-4b-instruct-2507-q4_k_m, 127.0.0.1:8187)
Agent        OK
Retrieval    OK   (hybrid_rerank)
Reranker     OK
Interface    OK   http://127.0.0.1:8790
API          OK   http://127.0.0.1:8790/api  (health, status, chat)
LLM distant  desactive
Phase        PHASE_4_FROZEN
Statut       NO-GO PROVISOIRE
```

Un composant indisponible s'affiche `KO` (jamais « OK » parce que le code existe). Sans llama-server, l'interface reste utilisable pour les textes retrouvés et affiche à l'utilisateur « Le service de rédaction des réponses est momentanément indisponible. » ; le message d'administration « Le modèle local n'est pas disponible. Veuillez démarrer llama-server. » reste réservé à `/api/status` et aux scripts (l'interface publique n'affiche aucun détail technique, voir LOCAL_UI.md § 2).

## 5. Arrêt

```powershell
.\stop_local.ps1                  # [-KeepLlm]
```

N'arrête **que** les processus enregistrés par `start_local.ps1` (PID **et** heure de démarrage contrôlés, pour ne jamais frapper un PID réutilisé). Un llama-server lancé par ailleurs, les autres Python, Grafana, etc. ne sont pas touchés. Un llama-server démarré par `start_local.ps1` est arrêté avec l'application, sauf `-KeepLlm`. Une instance lancée à la main (`python -m local_app`) n'est pas enregistrée : on l'arrête avec Ctrl+C.

## 6. Configuration

Valeurs par défaut sûres ; rien n'est à régler. Variables **de l'application** (jamais lues par le moteur) :

| Variable | Effet | Défaut |
|---|---|---|
| `LOCAL_APP_PORT` | port (1024-65535) ; `-Port` de `start_local.ps1` | 8790 |
| `LOCAL_APP_RUNTIME` | dossier des journaux et PID | `local_app\runtime` |
| `LOCAL_APP_LOG_QUESTIONS=1` | écrit le **texte** des questions dans le journal (voir § 9) | désactivé |
| `LOCAL_APP_DEBUG=1` | développement : ajoute aux réponses les champs internes (scores) et journalise les piles d'erreur | désactivé |
| `LOCAL_APP_ALLOW_ENV_OVERRIDES=1` | autorise de démarrer malgré une variable de moteur (signalé dans l'état) | désactivé |

**Garde-fous d'environnement** (au démarrage, sur le processus de l'application seulement) :

* l'application **refuse de démarrer** si l'une de ces variables est définie, car elle ne servirait plus `PHASE_4_FROZEN` : `AGENT_RR_MIN`, `AGENT_W_RERANK`, `AGENT_RERANK_N`, `AGENT_LANGS`, `AGENT_RERANK_DIR`, `AGENT_RERANK_MODEL`, `AGENT_EMBED_DIR`, `AGENT_VECTOR_DIR`, `AGENT_JSON_SCHEMA`, et `AGENT_RETRIEVER` sauf `auto`/`hybrid_rerank` ;
* le LLM est **toujours local** : `AGENT_LLM` est forcé à `local`, et `AGENT_ALLOW_REMOTE_LLM`, `ANTHROPIC_API_KEY`, `AGENT_MODEL` sont retirés de l'environnement du processus (leur nom est journalisé, jamais leur valeur) ;
* `AGENT_LOCAL_URL`, s'il est défini, doit désigner `127.0.0.1`, `localhost` ou `::1` (sinon refus de démarrer).

Limites de validation : question de 3 à 500 caractères (la limite de l'ancienne interface), corps de requête ≤ 8 Ko.

## 7. API

Même origine que l'interface. Toutes les erreurs ont la forme `{"error": {"code": "...", "message": "..."}}` (message en français, sans chemin, sans pile d'erreur).

| Route | Rôle |
|---|---|
| `GET /api/health` | `{"status":"ok"}` : le processus répond |
| `GET /api/status` | état **contrôlé** : `phase`, `status`, `status_reasons`, `freeze` (empreinte du manifeste), `app.state` (`starting`/`ready`/`degraded`/`error`), `agent`, `retrieval` (`ready`, `engine`, `fallback`), `reranker`, `llm` (`online`, `model`, `local_only`, `message`), `corpus`, `remote_llm`, `ocr_experimental`, `ocr_uncertain_active`, `limits` |
| `POST /api/chat` | corps `{"question": "..."}` (aucun autre champ accepté) |

Réponse de `/api/chat` : celle de l'agent, sans les champs internes, plus `status` (`answered`, `refused`, `clarification`, `llm_unavailable`), `llm` (`requested`, `available`, `message`), `durations_ms` (`api`, `pipeline`, `retrieval`, `reranking`, `generation`) :

```json
{"question": "...", "status": "answered", "found": true, "clarify": false, "mode": "llm", "reason": "ok",
 "answer": "... [S1].", "citations": [ {source} ], "sources": [ {source}, ... ], "notes": ["..."], "disclaimer": "...",
 "model": "qwen3-4b-instruct-2507-q4_k_m (local, CPU)", "provider": "local", "retriever": "hybrid_rerank", "latency_s": 20.1,
 "timings": {"embed_question_ms": 6.3, "search_ms": 0.8, "rerank_ms": 444.1, "total_ms": 454.4},
 "durations_ms": {"api": 20578, "pipeline": 20546, "retrieval": 10.3, "reranking": 444.1, "generation": 20100},
 "llm": {"requested": true, "available": true, "message": null}}
```

Quand il n'y a pas de réponse directe mais que des textes ont été retrouvés (`status` = `llm_unavailable`, ou `refused` avec des sources), la réponse contient aussi `texts_intro` (« Je ne peux pas répondre directement, mais voici quelques textes qui pourraient vous aider à trouver la réponse : ») et `texts` : les passages **regroupés par texte** (`reference`, `titre`, `type`, `date`, `statut_juridique`, `statut_detail`, `statut`, `relations`, `alerte`, `document_url`, `source_url`, `passages` = `[{id, emplacement, page}]`), construits **à partir des seules métadonnées** (aucun LLM, aucun extrait). Sinon `texts` = `[]` et `texts_intro` = `null`.

Source : `id, chunk_id, texte, titre, type, article, emplacement, chapitre, section, page, page_fin, date, statut, statut_juridique, statut_detail, statut_confiance, relations, alerte, via, autres_copies, extraction, a_verifier, ocr_uncertain, extrait, document_url, source_url`.

* `status` ne fait que nommer la sortie de l'agent : `answered` = `mode:"llm"` et `found:true` ; `refused` = `found:false` ; `clarification` = `clarify:true` ; `llm_unavailable` = recherche trouvée mais aucune génération (llama-server éteint, réponse illisible…).
* `retrieval` = durée du moteur hors reranking ; `generation` = `latency_s` mesurée par l'agent (précision 0,1 s) ; `api` = durée totale de la requête (validation, sonde du LLM, mise en forme comprises).
* Les notes de l'agent sont conservées, mais les mentions internes (chemin d'un fichier, nom de script, type d'exception) sont remplacées par un message utilisateur.

Codes d'erreur : `400` `invalid_request` / `invalid_json` / `empty_question` / `question_too_short` / `invalid_question` ; `422` `question_too_long` ; `413` `payload_too_large` ; `415` `unsupported_media_type` ; `429` `busy` ; `503` `warming_up` (moteur en chargement) / `agent_unavailable` ; `500` `internal_error` ; `403` `forbidden_host` / `forbidden_origin` ; `404` ; `405`.

## 8. Sécurité (vérifications réelles : voir § 12)

* **Écoute locale seulement par défaut** : `127.0.0.1` (constante du code). Vérifié au niveau du système (sockets en écoute de l'application et de llama-server). Une **option explicite** (`-Lan`, § 15) ajoute l'écoute sur l'adresse privée de la machine, avec code d'accès ; llama-server reste sur `127.0.0.1` dans tous les cas.
* **Aucune requête sortante** : le serveur ne contacte que 127.0.0.1:8187 (llama-server) ; l'échantillonnage des connexions de son processus pendant une vraie question n'a vu que des adresses de bouclage. Le navigateur n'a besoin d'aucune ressource externe (test avec un navigateur dont toute résolution DNS externe échoue).
* **Pas de télémétrie, pas d'analyse, pas de CDN, pas de script distant** ; politique CSP stricte (`default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'…`) ; pas de style ni de script en ligne.
* **LLM distant désactivé** : aucune API OpenAI/Anthropic n'est appelée ; même si l'environnement demande `AGENT_LLM=anthropic`, l'application force le LLM local (testé avec une fausse clé). Aucune clé n'existe dans l'interface ni dans les réponses (balayage automatique).
* **Même origine, pas de CORS** : aucun en-tête `Access-Control-*` n'est jamais émis. L'en-tête `Host` doit être `127.0.0.1:PORT`/`localhost:PORT` (contre le « DNS rebinding »), `Origin` doit être l'application elle-même, `Sec-Fetch-Site` inter-sites est refusé : un site visité dans le navigateur ne peut pas interroger l'API.
* **Validation stricte** : JSON `application/json` obligatoire, un seul champ `question`, texte de 3 à 500 caractères sans caractère de contrôle, corps limité à 8 Ko.
* **Rien d'interne exposé** : ni chemin Windows, ni pile d'erreur, ni variable d'environnement, ni prompt, ni score interne, ni nom de script. Les erreurs inattendues renvoient un message générique ; le détail minimal est dans le journal local.
* **Interface** : tout texte du corpus ou du modèle est inséré par `textContent` (test avec un extrait contenant `<img onerror>` et `<script>` : rien ne s'exécute).
* Les liens « PDF officiel » ouvrent le site de la Banque d'Algérie **à la demande de l'utilisateur** (clic) : c'est la seule fonction qui demande Internet, et elle est exécutée par le navigateur, pas par l'application.

## 9. Journaux (local, rien n'est envoyé)

Dossier `local_app\runtime\` (créé à l'exécution, hors du système gelé) :

| Fichier | Contenu |
|---|---|
| `api.log` | une ligne JSON par événement ; pour chaque question : horodatage, `status`, **nombre de caractères** de la question, nombre de sources, moteur, durées (`embed_ms`, `retrieval_ms`, `rerank_ms`, `generation_ms`, `total_ms`), état du LLM. Rotation 1 Mo × 3. |
| `access.log` | journal d'accès HTTP : méthode, chemin, code (jamais le corps des requêtes). Rotation 500 Ko × 2. |
| `server.out.log`, `server.err.log` | sortie du processus (erreurs de démarrage) |
| `pids.json` | PID et heure de démarrage des processus lancés par `start_local.ps1` |

**Le texte des questions n'est pas journalisé par défaut** : une question juridique peut être sensible et le journal n'a pas besoin de la contenir pour mesurer ou diagnostiquer. `LOCAL_APP_LOG_QUESTIONS=1` l'y écrit en clair, à n'utiliser que pour une analyse ponctuelle (puis supprimer `api.log`). L'historique de l'interface (questions **et réponses**) est, lui, dans le navigateur de l'utilisateur (voir LOCAL_UI.md § 6). Le journal de llama-server est celui de `llm_local\start_server.ps1` (`D:\llm\bench\server.log`).

## 10. Fonctionnement hors ligne

Tout fonctionne sans Internet : modèles, corpus, index, LLM et interface sont locaux ; l'interface ne charge ni police ni script ni image distants. Seuls les liens vers les PDF officiels (clic) exigent une connexion.

## 11. Diagnostic

| Symptôme | Cause probable | Action |
|---|---|---|
| `le port N est deja utilise par 'X'` | un autre programme écoute (ex. 3000 Grafana, 8000 IncrediBuild) | `-Port 8791` ; ne pas arrêter l'autre programme |
| `variable(s) d'environnement qui modifient le systeme fige` | `AGENT_RR_MIN`… définie dans la session | `Remove-Item Env:NOM`, nouvelle session |
| `fichier(s) requis introuvable(s)` | modèle, vecteurs ou corpus déplacés | restaurer (sauvegarde : `D:\llm\snapshots\phase4_frozen_backup`) ; `freeze_phase4 verify` dit quoi |
| « Le service de rédaction des réponses est momentanément indisponible. » (interface) / « Le modèle local n'est pas disponible… » (`/api/status`) | llama-server éteint (il s'arrête à la fermeture de la session qui l'a lancé) | `.\llm_local\start_server.ps1` ou relancer `start_local.ps1` |
| Pied de page « Retrieval : mode dégradé » | le moteur a basculé sur la recherche lexicale de repli (vecteurs ou modèle introuvables) | résultats moins fiables ; corriger la cause (voir `server.err.log`, `api.log`), redémarrer |
| `503 warming_up` | moteur en cours de chargement (quelques secondes après le démarrage) | attendre |
| `429 busy` | une question est en cours | attendre sa fin |
| `503 agent_unavailable` | index/modèles illisibles | `api.log`, `freeze_phase4 verify` |
| Page « injoignable » | application arrêtée | `.\start_local.ps1` |
| `L'application s'est arretee (code …)` | erreur au démarrage | lire les dernières lignes affichées et `local_app\runtime\server.err.log` |
| Plusieurs minutes de réponse | CPU saturé (autre programme, ex. Discord ~4 Go de RAM) | libérer la machine ; ne pas lancer de crawl/build en parallèle |

## 12. Tests et vérifications

```powershell
python local_app/tests/test_api.py          # API, faux agent, sans modèle : « Tests API : X/Y »
python local_app/tests/test_ui.py           # interface dans Edge/Chrome sans fenêtre : « Tests UI : X/Y »
python local_app/tests/test_lan.py          # mode réseau optionnel (§ 15) : code d'accès, sessions, blocage, hôtes, liaisons : « Tests réseau : X/Y »
python local_app/tests/test_integration.py  # RÉEL : navigateur → API → agent → retrieval → reranker → llama-server (llama-server en ligne)
                                            #   (LOCAL_APP_URL=http://127.0.0.1:8790 pour viser le déploiement déjà démarré)
python -m agent_fr.eval.human.freeze_phase4 verify   # le système gelé n'a pas bougé
```

Résultats au 7 octobre 2026 (sur le déploiement démarré par `start_local.ps1`) : **API 41/41 ; UI 23/23 ; intégration 13/13 ; freeze verify : aucun écart**. L'intégration vérifie notamment que la réponse de l'API est identique, mot pour mot, à celle de `agent.ask` appelé directement (mêmes sources, mêmes notes), que le serveur n'écoute que sur 127.0.0.1, qu'aucune connexion hors boucle locale n'apparaît pendant une vraie question, et que `/api/health` reste disponible pendant la génération.

## 13. Mise à jour

* **De cette couche** (API, interface, scripts) : `.\stop_local.ps1` → remplacer `local_app\`, `start_local.ps1`, `stop_local.ps1` → relancer les trois suites de tests → `freeze_phase4 verify` → `.\start_local.ps1`.
* **Du système gelé** (moteur, corpus, modèles, règles) : hors de ce document et **interdit** tant que le juriste n'a pas répondu ; la sortie du gel suit `docs/PHASE_4_FROZEN.md` § 7 (un nouveau gel porterait un autre nom). Après un futur nouveau gel, l'application n'a rien à changer : elle lit le statut et la phase dans le marqueur et le manifeste.

## 14. Retour arrière

`.\autostart.ps1 -Uninstall` (si la tâche planifiée a été installée), `.\stop_local.ps1` (et `.\lan_firewall.ps1 -Remove` si la règle du pare-feu a été créée), puis supprimer `local_app\`, `start_local.ps1`, `stop_local.ps1`, `lan_firewall.ps1`, `autostart.ps1`, `keep_running.ps1`, `docs\LOCAL_DEPLOYMENT.md`, `docs\LOCAL_UI.md`. Rien d'autre n'a été créé ni modifié dans le projet : le système gelé est strictement identique (vérifiable par `freeze_phase4 verify`). L'ancienne interface (`python -m agent_fr --serve`, port 8765) et `llm_local\start_server.ps1` fonctionnent comme avant. L'historique de l'interface vit dans le navigateur (le vider : bouton « Effacer l'historique »).

## 15. Accès depuis le réseau local (option `-Lan`, désactivée par défaut)

Permet à des collègues du même réseau d'utiliser l'assistant **depuis leur navigateur**, sans rien installer. Ce n'est pas un partage de fichiers : l'application tourne sur CETTE machine (processeur, mémoire et modèle de cette machine) ; les autres ne font qu'afficher la page.

```powershell
.\lan_firewall.ps1               # facultatif, administrateur : règle étroite du pare-feu Windows (voir « Pare-feu » ci-dessous)
.\start_local.ps1 -Lan           # [-AccessCode CODE] [-LanIp 10.x.y.z]
```

Le script affiche les adresses (`http://NOM-COMPLET:8790` en premier, puis `http://NOM-COURT:8790` et `http://ADRESSE-IP:8790`) et le **code d'accès**, une seule fois. **Préférer le nom complet** (ex. `s-mabed.bank-of-algeria.dz`) : il est enregistré dans le DNS de l'entreprise, il est accepté tel quel par l'application et il correspond aux exceptions habituelles de proxy (`*.domaine`) ; le nom court dépend de la liste de suffixes DNS du poste appelant, et une adresse IP peut être envoyée au proxy de l'entreprise, qui ne la joindra pas. Les collègues ouvrent l'adresse, saisissent le code, puis utilisent l'interface normale. Retour au mode local : `.\stop_local.ps1` puis `.\start_local.ps1`.

**Garde-fous**

| Garde-fou | Détail |
|---|---|
| Désactivé par défaut | sans `-Lan`, rien ne change : écoute sur `127.0.0.1` seulement, aucun code |
| Une seule adresse réseau | l'application écoute sur `127.0.0.1` **et** sur l'adresse privée choisie (détectée sur la carte du réseau d'entreprise, ou `-LanIp`), **jamais sur toutes les cartes** : les cartes VMware et Hyper-V ne sont pas exposées. Refus d'une adresse publique, de la boucle locale ou d'une adresse inconnue |
| Code obligatoire par défaut | 8 caractères au minimum (12 caractères aléatoires lisibles générés par défaut, ~59 bits). Sans code valide l'application refuse de démarrer, **sauf choix explicite** `-Lan -NoCode` (accès libre, voir ci-dessous). Comparaison en temps constant, jamais journalisé |
| Tout est derrière le code | page, scripts et API ; seules la page d'accès, sa feuille de style et la sonde `/api/health` (qui répond « ok ») restent publiques. Le code s'applique aussi à `127.0.0.1` |
| Sessions | cookie aléatoire de 12 h, `HttpOnly`, `SameSite=Strict` ; une session expirée renvoie à la page d'accès |
| Essais limités | 5 codes faux depuis une même adresse bloquent cette adresse 5 minutes |
| Noms d'hôte | l'en-tête `Host` doit être un nom de cette machine (nom court, nom complet, adresse) ; garde contre le « DNS rebinding » conservée. Noms supplémentaires : `LOCAL_APP_LAN_HOSTS=nom1,nom2` |
| Une question à la fois | un collègue qui arrive pendant une génération reçoit « Une question est déjà en cours de traitement (peut-être celle d'un autre utilisateur). Réessayez dans quelques secondes. » (une réponse prend ~20 s sur ce processeur) |
| Pas de nouvelle donnée collectée | le texte des questions n'est toujours pas journalisé ; seuls les essais de connexion (réussis ou non) sont journalisés avec l'adresse de la machine appelante |

**Accès libre (`-Lan -NoCode`).** Choix explicite de l'utilisateur : aucune page de code, tout poste qui connaît l'adresse utilise l'assistant. Restent actifs : adresse privée uniquement, contrôle de l'en-tête `Host`, de l'origine et de `Sec-Fetch-Site`, une seule question à la fois. N'est plus protégé : l'usage (n'importe qui sur le réseau peut interroger l'assistant, consommer le processeur de la machine et occuper l'unique file de questions). `LOCAL_APP_LAN_NO_CODE=1` n'a d'effet que si aucun code n'est fourni ; un code fourni l'emporte toujours. Passer de l'un à l'autre : `.\stop_local.ps1`, puis `.\start_local.ps1 -Lan` (avec code) ou `.\start_local.ps1 -Lan -NoCode`.

**Pare-feu.** `lan_firewall.ps1` crée la règle la plus étroite possible : entrant, TCP, **ce port seulement**, profil **Domaine** seulement, depuis le **sous-réseau local** seulement, pour le **programme Python du projet** seulement ; `-Remove` la supprime. Si le pare-feu Windows est désactivé sur la machine (c'est le cas sur la machine d'origine), la règle est sans effet et le port est joignable par tout le réseau : le code d'accès est alors la seule protection ; `start_local.ps1 -Lan` l'indique.

**Ce que cette option ne fait pas.** Pas de chiffrement (HTTP) : questions et réponses circulent en clair sur le réseau, ce qui se limite ici à des questions sur des textes publics ; pas de comptes individuels (un code partagé, à changer en relançant) ; serveur de développement Werkzeug, adapté à quelques testeurs et pas à un large public ; la machine doit rester allumée, session ouverte, application lancée (`llama-server` s'arrête à la fermeture de la session qui l'a démarré). Elle ne rend pas Internet accessible : toute adresse non privée est refusée.

**Organisation.** Sur une machine d'entreprise (domaine, politique de sécurité), exposer un service sur le réseau est une décision de la sécurité informatique, pas seulement de l'utilisateur de la machine. L'interface garde l'avertissement « projet éducatif non officiel » et la page d'accès le répète.

**Vérifié le 13 octobre 2026** : `test_lan.py` 14/14 (faux agent, aucune adresse réelle) ; démarrage réel avec `-Lan` sur l'adresse du réseau d'entreprise de cette machine, puis, **depuis cette même machine** (pas depuis un autre poste) : redirection vers la page d'accès sans session, 401 sur l'API, 403 pour un en-tête `Host` usurpé, refus d'un faux code, ouverture d'une session avec le bon code, accès par le nom de la machine, vraie question posée par ce chemin et répondue ; sockets en écoute : `127.0.0.1:8790` et `<adresse du réseau>:8790` uniquement ; en mode local par défaut, test d'intégration 13/13 (écoute sur la boucle locale seulement) et test d'interface 23/23. **Non vérifié** : la connexion réelle depuis une autre machine (c'est l'objet de l'essai demandé à un collègue).

## 16. Limites connues

Une seule question à la fois ; pas de flux ni d'annulation (le pipeline gelé n'en fournit pas) ; pas de mémoire de conversation ; `werkzeug` est un serveur de développement, suffisant pour un usage mono-utilisateur sur 127.0.0.1 mais à ne pas exposer ; interface testée seulement sous Edge/Chrome. Les limites et cas connus du système lui-même (H120, H129, conflits de dates FR/AR, OCR arabe, validation humaine absente) restent ceux de `docs/PHASE_4_FROZEN.md` et `docs/NOTE_AU_JURISTE.md`.

## 17. Garder le service allumé en continu (`autostart.ps1`)

Un service lancé depuis une fenêtre ou depuis un outil (par exemple l'application Claude) s'arrête avec elle : c'est ce qui s'est produit le 14 octobre 2026 quand cette application a redémarré. `autostart.ps1` installe un **superviseur** indépendant :

```powershell
.\autostart.ps1 -Install -Lan -NoCode     # ou -Lan -AccessCode CODE, ou sans -Lan (mode local seulement)
.\autostart.ps1 -Status                   # tâche, superviseur, état du service, fin du journal
.\autostart.ps1 -Resume                   # relève un arrêt manuel
.\autostart.ps1 -Uninstall                # supprime la tâche et arrête le service
```

| Élément | Détail |
|---|---|
| Tâche planifiée | une seule, nommée « RegAssist DZ keep running », au nom de l'utilisateur courant, déclenchée **à l'ouverture de session**, sans droit d'administrateur et sans mot de passe stocké ; relancée toutes les minutes si elle s'arrête ; sans limite de durée ; pas d'arrêt sur batterie |
| Superviseur `keep_running.ps1` | toutes les 30 s il teste l'application (`/api/health`) et le modèle (`llama-server /health`) ; après **2 contrôles ratés** il arrête ce que `start_local.ps1` avait lancé puis le relance avec les mêmes options. Journal : `local_app\runtime\keep_running.log` (200 Ko au plus, le code d'accès n'y figure jamais) |
| Arrêt manuel respecté | `.\stop_local.ps1` laisse un drapeau (`local_app\runtime\stopped_by_user.flag`) : le superviseur ne relance plus rien tant que `.\autostart.ps1 -Resume` ou un `.\start_local.ps1` manuel ne l'a pas levé |
| Hors de toute fenêtre | le service est un descendant du Planificateur de tâches (`svchost` → `powershell` du superviseur), pas de l'application qui l'a installé |

**Ce que ça garantit, et ce que ça ne garantit pas.** Le service reste allumé session **verrouillée** ou non, et revient seul après un plantage (~1 minute) ou après la fermeture d'une fenêtre. Il s'arrête à la **fermeture de session**, à l'arrêt ou au redémarrage de Windows, et ne repart qu'à la **prochaine ouverture de session** de l'utilisateur. Le rendre disponible avant toute ouverture de session exigerait une tâche système avec droits d'administrateur et un compte stocké, ou l'ouverture automatique de session : ce sont des choix de sécurité de l'organisation et ils ne sont pas faits ici. Avec `-AccessCode`, le code fait partie de la commande de la tâche (lisible par l'utilisateur et les administrateurs de la machine) ; avec `-NoCode`, aucun secret n'est stocké.

**Vérifié le 14 octobre 2026** : installation sans droit d'administrateur ; service démarré par la tâche ; descendance du processus vérifiée (Planificateur de tâches, aucune dépendance à l'application Claude) ; plantage simulé (processus tué) → service de retour en 66 s ; arrêt manuel respecté (aucune relance après 80 s) puis `-Resume` → service de retour en 56 s. **Non vérifié** : le comportement après fermeture de session / redémarrage de Windows (il repose sur le déclencheur « à l'ouverture de session » de la tâche planifiée).
