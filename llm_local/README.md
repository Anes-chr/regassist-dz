# LLM local (Qwen3-4B-Instruct-2507, CPU) — installation, benchmark, intégration

Tout est installé sous `D:\llm` (rien d'important sur C:). Les mesures ci-dessous ont été faites sur : Windows 10, Intel i7-13700 (16 cœurs / 24 threads,
sans AVX-512), 15,6 Go de RAM, **aucun GPU NVIDIA**.

## Ce qui est installé

| Élément | Détail |
|---|---|
| Moteur | `llama.cpp` **build b11411**, release officielle GitHub `ggml-org/llama.cpp` (zip CPU x64, 18,5 Mo), empreinte SHA-256 vérifiée contre celle publiée par GitHub. Dossier : `D:\llm\llama.cpp\b11411`. Backend CPU chargé automatiquement : `ggml-cpu-haswell` |
| Modèle | `Qwen3-4B-Instruct-2507`, GGUF **Q4_K_M** (2 497 281 120 octets = 2,32 GiB), licence **Apache-2.0**. Dossier : `D:\llm\models`. SHA-256 vérifié (`3605803b…e597`) |
| Provenance du modèle | quantification publiée par **unsloth** (`unsloth/Qwen3-4B-Instruct-2507-GGUF`). Le dépôt officiel `Qwen/…-GGUF` renvoyait 401 au moment de l'installation : ce n'est donc **pas** le fichier de l'éditeur du modèle, mais une conversion communautaire très utilisée |
| Serveur | `llama-server` (API compatible OpenAI) sur `127.0.0.1:8187` uniquement. Le port 8080 est déjà occupé par le système (HTTP.sys) |

## Utiliser

```powershell
.\llm_local\start_server.ps1                 # démarre le serveur (8 threads, contexte 4096) — ~4 s
python -m agent_fr --local-llm "question"     # l'agent rédige sa réponse avec le LLM local
Get-Process llama-server | Stop-Process       # arrêter le serveur (libère ~2,8 Go)
```
Variables : `AGENT_LLM=local|anthropic` (défaut `anthropic`, comportement d'origine inchangé), `AGENT_LOCAL_URL`, `AGENT_LOCAL_MODEL_NAME`.
Si le serveur n'est pas lancé, l'agent retombe automatiquement sur la réponse extractive (avec une note).

## Réglages mémoire retenus (mesurés, pas supposés)

| Réglage | Effet mesuré |
|---|---|
| `-lm none` (pas de mappage du fichier) | pic RAM du processus **4,2 Go → 2,5 Go**, vitesse identique (la version par défaut « repack » doublait l'occupation) |
| `-cram 256` | le cache de prompts vaut **8 192 Mo par défaut** : le serveur grimpait à 4,3-4,5 Go pendant un test |
| `-c 4096`, cache KV `q8_0`, `-fa on` | serveur stable à **2,75–3,0 Go** pendant 40 requêtes |
| `-b 512 -ub 128` | tampons de calcul réduits |

Deux **arrêts de sécurité** (RAM disponible < 400 Mo) se sont déclenchés avant ces réglages ; aucun depuis.

## Benchmark CPU (llama-bench, pp512 / tg128, 3 répétitions, mêmes réglages mémoire)

| Threads | Prompt tok/s | Génération tok/s | Pic RAM | RAM système mini dispo | Durée |
|---:|---:|---:|---:|---:|---:|
| 4 | 78,0 ± 2,6 | 13,09 ± 0,09 | 2 535 Mo | 1 873 Mo | 57,7 s |
| 8 | 101,2 ± 0,6 | 14,24 ± 0,47 | 2 536 Mo | 1 856 Mo | 49,7 s |
| 12 | 112,7 ± 6,9 | 14,06 ± 0,35 | 2 538 Mo | 2 156 Mo | 48,2 s |
| 16 | 127,9 ± 15,5 | 14,84 ± 0,20 | 2 540 Mo | 2 111 Mo | 44,4 s |

Lecture : la **génération plafonne vers 14 tok/s dès 4-8 threads** (limitée par la bande passante mémoire, pas par le nombre de cœurs). Seule la lecture du
prompt progresse avec les threads (+26 % de 8 à 16). **Recommandation : 8 threads** — la génération est déjà à 96 % du maximum et 16 threads logiques restent libres
pour que le PC reste fluide. 16 threads ne se justifient que pour de longs prompts répétés.

## Baseline qualité locale (reproductible, **non scientifique**)

`python llm_local/bench_quality.py --runs 2` — 22 prompts (FR, AR, technique, instructions, raisonnement), notation automatique par règles
(`scoring.py`). Résultat (2 passages) : **français 10/10, arabe 10/10, instructions 10/10, technique 7/10, raisonnement 1/4 à 450 tokens**.
Les échecs de raisonnement viennent de la **coupure à 450 tokens** : relancé avec 1 200 tokens (`reasoning_check.py`), **6/6 corrects** (réponses de ~520 tokens).
Autres échecs techniques : définition du ratio de solvabilité sans les mots attendus (1 prompt × 2), calcul 115 000 DA correct une fois sur deux.
**Reproductibilité** : à température 0, seules 4 réponses sur 22 sont strictement identiques entre deux passages (le cache de prompt modifie légèrement le
calcul) ; les verdicts, eux, sont presque toujours les mêmes.

Latence mesurée (serveur, 8 threads) : premier token 0,1–0,6 s sur prompts courts ; génération 14,5 tok/s ; une réponse de 450 tokens ≈ 31 s.

## Jeu AVEUGLE (à ne jamais utiliser pour l'entraînement)

`agent_fr/eval/llm_blind/` — 40 items : 8 français, 8 arabe, 8 instructions, 8 « citer une source » (vrais passages du corpus), 8 « je ne sais pas ».
`manifest.json` donne l'empreinte du jeu, la liste de questions et de passages à exclure ; `leak_check.py` **refuse** tout jeu d'entraînement qui les contient
(testé : fuite détectée, jeu propre accepté). Lancer : `python llm_local/run_blind.py --tag <nom>`.

**Qwen3-4B de base : 38/40** (arabe 8/8, français 8/8, citation 8/8, instructions 7/8, « je ne sais pas » 7/8), latence médiane 5,8 s.
Les deux défauts sont des défauts de **comportement/format**, justement ceux qu'un fine-tuning ciblé pourrait corriger :
1. B021 : on demandait un tableau JSON de 3 *chaînes*, le modèle a renvoyé 3 objets ;
2. B038 : sur une question sans réponse dans la source, le modèle écrit « non précisé » mais avec `found=true` + citation, au lieu du refus exact.
La notation était d'abord trop indulgente sur B021 (seul le nombre d'éléments était vérifié) : corrigée, jeu régénéré, baseline refaite.

## Intégration avec l'agent

`agent_fr/llm_backends.py` : fournisseurs interchangeables (`anthropic` | `local`) ; `answer.llm()` n'a plus de code spécifique à un fournisseur.
Profil local : 4 sources de 1 000 caractères + jusqu'à 2 textes modificateurs, 600 tokens de sortie max, JSON imposé (`response_format`).

**Défaut trouvé pendant l'intégration, corrigé** : sur « plafond d'indemnisation par déposant », l'agent avec le LLM local répondait **600 000 DA** (texte de 1997,
abrogé) car le texte de 2018 (2 000 000 DA) n'était pas dans les sources lues. Corrections : (1) les textes modificateurs sont toujours fournis au modèle,
(2) consigne explicite de ne jamais donner comme actuelle la valeur d'un texte « abrogé/modifié par », (3) réserve automatique ajoutée à la réponse si une source
citée est signalée modifiée/abrogée. Après correction : 2 000 000 DA, avec renvoi au règlement 2018-01.

## Agent complet + LLM local sur gold_v2 (62 questions, `python -m agent_fr.eval.llm_agent_eval`)

| Jeu | Fait clé dans la réponse | Source attendue citée | Refus corrects (pièges) |
|---|---|---|---|
| dev | 12/18 | 11/18 | — |
| test | 16/20 | 16/21 | 8/8 |
| holdout | 10/13 | 12/13 | 2/2 |

Latence de bout en bout (recherche + lecture de ~1 400 tokens de sources + rédaction ~100 tokens) : **médiane 31 s, p90 68 s, maximum 93 s**.
Analyse des 17 échecs : **13 viennent de la recherche** (le bon passage n'était pas dans les 4 sources lues : le modèle répond alors à côté de la bonne règle ou
refuse à raison), **4 sont des réponses correctes reformulées** que la notation stricte compte à tort. Le LLM refuse **mieux** que la recherche seule les questions hors
sujet (ex. « billet d'avion Alger-Paris » : refusé), mais **ne peut pas retrouver ce que la recherche ne lui donne pas**. Conclusion : le goulot est la
**recherche sémantique**, pas le modèle de langage.

## Arbitrage vitesse / mémoire du cache KV (`ab_kv.py`, même prompt de 724 tokens)

| Config | Lecture du prompt (1ʳᵉ passe, à froid) | Génération | RAM serveur |
|---|---:|---:|---:|
| KV q8_0 + flash-attn (**défaut**) | 111 tok/s | 14,0 tok/s | 2,9 Go |
| KV f16 (auto) | 131 tok/s (+17 %) | 14,4 tok/s | 3,2 Go |
Les passes suivantes affichent ~50 tok/s : artefact du cache de prompt (seuls les tokens nouveaux sont comptés), pas une vraie baisse. Si vous avez > 5 Go libres, la
config f16 est un peu plus rapide ; sinon gardez le défaut.

## Limites assumées
* Pas de GPU : ~14 tok/s en génération ; une réponse de l'agent prend **20 à 60 s** (surtout la lecture des sources). L'interface web affiche donc d'abord
  les passages (instantané) puis la rédaction du LLM.
* Qwen3-4B est un petit modèle : il peut mal lire un passage ou en ignorer un. Il est borné par la recherche (BM25) qui lui fournit les sources.
* Notations automatiques : elles détectent des défauts probables, elles ne remplacent pas la relecture humaine.
