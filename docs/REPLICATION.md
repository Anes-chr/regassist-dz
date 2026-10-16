# Répliquer le projet sur une autre machine

Ce document décrit comment obtenir, sur une autre machine, **exactement** le système gelé `PHASE_4_FROZEN` (statut : NO-GO PROVISOIRE) et l'application locale. « Exactement » est vérifiable : `python -m agent_fr.eval.human.freeze_phase4 verify` compare le code, le corpus, les vecteurs, les jeux d'évaluation et les modèles aux empreintes SHA-256 du manifeste et doit répondre **« aucun écart »**.

> Ce dépôt public contient le code, l'interface, la suite d'évaluation et une copie structurée de textes publics de la Banque d'Algérie (corpus) à des fins de reproductibilité et de recherche éducative. Seul le texte officiel (PDF) fait foi (voir la section Gouvernance et Licences du README).

## 1. Ce qui est dans le dépôt, ce qui ne l'est pas

| Élément | Où | Taille | Comment l'obtenir |
|---|---|---|---|
| Code, tests, documentation, scripts | dépôt | quelques Mo | `git clone` |
| **Corpus officiel** (PDF/HTML sources, textes extraits, chunks, métadonnées, rapports) | `corpus/` | ≈ 940 Mo | `git clone` |
| État de collecte (pages, candidats, cache d'extraction) | `state/` | ≈ 70 Mo | `git clone` |
| Jeux et résultats figés de l'évaluation (TEST v1, résultats de la phase 4, fiches de relecture) | `agent_fr/eval/` | ≈ 40 Mo | `git clone` |
| **Vecteurs d'embeddings** (4 fichiers du gel + cache) et **instantané du corpus** `corpus_phase4` | `replication/` | ≈ 90 Mo | `git clone`, puis copie par `setup_machine.ps1` vers `D:\llm` |
| Modèles : multilingual-e5-small (ONNX), reranker mmarco (ONNX quantifié), Qwen3-4B-Instruct-2507 Q4_K_M | `D:\llm\models` | ≈ 3 Go | **téléchargés** par `setup_machine.ps1` (sources publiques, empreintes vérifiées) |
| llama.cpp b11411 (CPU x64) | `D:\llm\llama.cpp\b11411` | 19 Mo | **téléchargé** par `setup_machine.ps1` |
| Caches (`agent_fr/.cache`), journaux d'exécution (`local_app/runtime`) | — | — | recréés automatiquement, jamais versionnés |

Les modèles ne sont pas dans Git : le fichier ONNX d'embeddings (448 Mo) et le LLM (2,4 Go) dépassent la limite de 100 Mo par fichier de GitHub, et ce sont des fichiers publics de tiers. Le script les télécharge à leur source et refuse tout fichier dont l'empreinte diffère du manifeste.

## 2. Prérequis de la machine

| | Recommandé (estimation, non testé sur d'autres machines) | Machine d'origine (mesuré) |
|---|---|---|
| Système | Windows 10/11 x64, PowerShell 5.1 | Windows 10 Pro 19045 |
| Processeur | x64 **avec AVX2** (le reranker est le fichier `model_quint8_avx2.onnx`) | i7-13700, sans GPU |
| Mémoire | 8 Go recommandés (le LLM seul ≈ 2,5 Go, voir `llm_local/README.md`) | 15,6 Go |
| Disque | ≈ 6 Go libres (dépôt ≈ 1,1 Go + modèles ≈ 3 Go + marge) | — |
| Logiciels | Git, **Python 3.14.4**, `curl.exe` (présent dans Windows 10 ≥ 1803) | Python 3.14.4 |
| Facultatif | Node ≥ 22 + Edge/Chrome (tests de l'interface) ; Tesseract 5.5 + `ara`/`fra` (seulement pour refaire l'OCR du corpus) | — |
| Lecteur | un lecteur **`D:`** : le manifeste du gel et les scripts utilisent des chemins absolus `D:\llm\…`. Sans lecteur D: : `subst D: C:\donnees` | `D:` |

## 3. Procédure

```powershell
# 1. Cloner le dépôt — chemins longs activés pour le corpus
git config --global core.longpaths true
git clone https://github.com/SalimMabed/regassist-dz.git
cd regassist-dz

# 2. Dépendances Python (versions exactes du gel)
pip install -r requirements.txt

# 3. Contrôler ce qui manque, sans rien modifier
.\replication\setup_machine.ps1 -VerifyOnly

# 4. Installer : télécharge les modèles (~3 Go), copie les vecteurs et l'instantané ; demande confirmation avant de télécharger
.\replication\setup_machine.ps1
#    options : -SkipLlm (sans LLM ni llama.cpp), -WithOcr, -Yes (sans confirmation), -NoFreezeCheck

# 5. Vérifier l'identité avec le système gelé (le script la lance en dernière étape)
python -m agent_fr.eval.human.freeze_phase4 verify      # attendu : « RÉSULTAT : aucun écart »

# 6. Démarrer l'application locale
.\start_local.ps1                                        # puis http://127.0.0.1:8790
```

Si PowerShell refuse d'exécuter un script : `powershell -ExecutionPolicy Bypass -File .\replication\setup_machine.ps1`.

Le fichier `.gitattributes` du dépôt désactive toute conversion de fin de ligne (`* -text`). **Ne le retirez pas** : une conversion LF/CRLF modifierait les octets du corpus, donc les empreintes du gel et les clés des vecteurs.

## 4. Vérifier la réplication

| Test | Commande | Attendu |
|---|---|---|
| Identité avec le système gelé | `python -m agent_fr.eval.human.freeze_phase4 verify` | « aucun écart » |
| État des modèles et des données | `.\replication\setup_machine.ps1 -VerifyOnly` | « Tout est conforme au manifeste du gel. » |
| Application (sans modèle) | `python local_app/tests/test_api.py` | tous les tests passent |
| Application, interface | `python local_app/tests/test_ui.py` | tous les tests passent (Node + Edge/Chrome) |
| Chaîne réelle de bout en bout | `python local_app/tests/test_integration.py` | tous les tests passent (application démarrée, llama-server en ligne) |

## 5. Ce qui peut différer d'une machine à l'autre

* **Performances** : `llm_local/config.ps1` fixe 8 threads et un contexte de 4096. Ce fichier fait partie du gel : le modifier est détecté comme écart. Sur un processeur plus modeste, les réponses sont simplement plus lentes.
* **Ports** : 8790 (application), 8187 (LLM), 8765 (ancienne interface). Si un port est pris, `.\start_local.ps1 -Port 8791` ; le script nomme le programme qui l'occupe sans jamais l'arrêter.
* **Version de Python / des paquets** : celles du gel sont dans `requirements.txt` et le manifeste. Le script avertit si la version de Python diffère ; d'autres versions ne sont pas testées.
* **Corpus** : c'est l'instantané du 6-7 octobre 2026. Relancer la collecte (`boa_pipeline`) produirait un autre corpus, donc d'autres empreintes : ce n'est pas une réplication, c'est une mise à jour, hors du gel.

## 6. Limites de cette procédure

* Le **téléchargement** des modèles par `setup_machine.ps1` n'a pas été exécuté sur une machine vierge au moment de la rédaction. Ont été vérifiés : le mode `-VerifyOnly` sur la machine d'origine (tout conforme), la copie des vecteurs et de l'instantané vers une racine de test, et, pour chaque URL de téléchargement, que la taille annoncée par le serveur est exactement celle du manifeste (pour l'archive llama.cpp, qui n'y figure pas : celle de `llm_local/README.md`, 18,5 Mo). L'empreinte SHA-256 est contrôlée après chaque téléchargement.
* **Fin de ligne** : un clone Windows par défaut (`core.autocrlf=true`) a été simulé depuis le dépôt poussé. Avec le `.gitattributes` du dépôt, 60 fichiers contrôlés (code, corpus vivant, état de collecte) sont identiques aux empreintes du manifeste ; sans lui, 41 fichiers de code différaient. Un clone complet sur une machine vierge n'a pas encore été fait.
* Si un hébergeur de modèles change ou retire un fichier (le dépôt officiel `Qwen/…-GGUF` renvoyait déjà 401, d'où la source `unsloth`), le script s'arrête avec un message ; la source est alors à remplacer dans `replication/setup_machine.ps1` (tableau `$Models`) et l'empreinte du manifeste reste l'arbitre.
* Le statut du système ne change pas par réplication : **NO-GO PROVISOIRE**, validation juridique humaine absente.
