# Agent français — RegAssist DZ

Assistant de recherche dans les textes réglementaires de la Banque d'Algérie (corpus français, `corpus/chunks/chunks_fr.jsonl`).
Il **cite, ne conclut pas** : chaque réponse renvoie l'article, la page, le PDF officiel et la page du site.

## Lancer
```bash
python -m agent_fr "Que dit l'article 5 du règlement n° 14-02 ?"        # en ligne de commande
python -m agent_fr --serve                                                # interface web : http://127.0.0.1:8765
python -m agent_fr --eval                                                 # jeux de tests (rapport : corpus/reports/agent_eval.json)
python -m agent_fr --reindex                                              # forcer la reconstruction de l'index
python -m agent_fr --llm "question"                                       # rédaction par LLM (voir plus bas)
python tests/test_agent.py                                                # tests unitaires
```
L'index est reconstruit automatiquement quand `chunks_fr.jsonl` ou `documents_fr.json` change (mise à jour du corpus).

## Fonctionnement
1. **Références explicites** : « article 5 du règlement n° 14-02 » est résolu directement (numéro de texte tolérant 14-02 / 2014-02).
2. **Relations** : « quelle instruction abroge l'instruction n° 05-2016 ? » cherche les textes qui citent ce numéro avec ce verbe
   (relations extraites par le pipeline : intitulé = preuve forte, texte = à vérifier).
3. **Recherche libre (phase 2, par défaut `AGENT_RETRIEVER=auto`)** : BM25 + embeddings locaux multilingues (e5-small) fusionnés (RRF), logique temporelle (date de référence, versions remplacées,
   textes modificateurs), demande de précision pour les questions vagues, reranker cross-encoder local ; repli automatique sur l'ancien moteur BM25 (`legacy`) si les modèles ou vecteurs sont absents,
   `AGENT_RETRIEVER=legacy` pour le retour arrière. Doublons de copies regroupés (`autres_copies`). Détails et mesures : [RETRIEVAL_PHASE2.md](RETRIEVAL_PHASE2.md).
4. **Refus** : si les termes de la question ne sont pas retrouvés dans le meilleur passage, ou si le texte cité n'existe pas dans le corpus,
   l'agent répond « Je ne trouve pas de disposition correspondante dans le corpus disponible. »
5. **Statut** : toujours « STATUT À VÉRIFIER » sauf abrogation prouvée ; les textes liés (modifié par, abrogé par…) sont affichés.
6. **Confiance** : correspondance « partielle » signalée à l'utilisateur.

## Mode LLM (optionnel)
Définir la clé **dans votre environnement** (jamais dans le code ni dans une conversation) :
```bash
set ANTHROPIC_API_KEY=...        # PowerShell : $env:ANTHROPIC_API_KEY="..."
set AGENT_MODEL=claude-sonnet-5-5   # facultatif
python -m agent_fr --llm "question"
```
Le modèle ne reçoit que les passages récupérés (balises `<source>`, `<` neutralisés), doit citer `[S1]…`, refuse hors sources, ne qualifie
jamais un texte « en vigueur ». Contrôles côté code : citations hors passages ignorées ; numéro d'article mentionné mais absent des
passages → avertissement. **Ce chemin est testé avec un faux client (tests/test_agent.py), pas encore avec la vraie API.**

## Mesures actuelles (python -m agent_fr --eval)
Jeu `agent_fr/eval/gold_v2.jsonl` : 62 questions écrites et **relues par Claude (assistant IA) contre le texte extrait — pas par un juriste humain**.
Chaque réponse attendue est vérifiée mécaniquement (le passage existe et contient le fait clé).

| Jeu | n | Bon passage dans la réponse affichée | En 1ʳᵉ position | Refus corrects (pièges) |
|---|---|---|---|---|
| dev (a servi à régler l'agent) | 18 | 14/18 | 9/18 | — |
| test (écrit avant les derniers réglages ; ses échecs ont été consultés) | 21 | 18/21 | 11/21 | 7/8 |
| **holdout aveugle** (écrit après le réglage, mesuré une fois) | 13 | **13/13** | 10/13 | 1/2 |

Lecture honnête : le holdout est **optimiste** (questions écrites en lisant le texte, donc proches de son vocabulaire). Le jeu « test »,
plus reformulé, donne **≈ 85 % de présence et ≈ 50 % en 1ʳᵉ position**. Un utilisateur réel reformule davantage.
Autres jeux : références (300 requêtes synthétiques) textes 147/150, articles 150/150 ; audit des citations ci-dessous.

**Audit des citations** (`python -m agent_fr.audit`) : sur 7 596 passages non-OCR, 7 570 sont retrouvés mot pour mot à la page annoncée du PDF,
26 diffèrent en bordure, **0 introuvable** ; 189 passages OCR non vérifiables. Contrôle visuel de la loi 23-09 (deux colonnes) : conforme.

**Textes évolutifs** : une question comme « plafond d'indemnisation par déposant » retombait sur 600 000 DA (règlement 2004) alors que
2 000 000 DA s'applique depuis 2018/2020. L'agent remonte maintenant le texte modificateur et alerte quand un texte cité est modifié/abrogé
(« anciens textes signalés » : 3/3 dev, 2/2 test). Cela dépend de la détection des relations ; deux défauts ont été trouvés et corrigés
pendant cette relecture (formule passive après une date hégirienne ; date divergente entre le libellé du site et le texte citant).

**Essais négatifs** : l'expansion de requête par pseudo-retour de pertinence (testée à 4 poids) dégrade le rang 1 sur le jeu dev : désactivée
(`PRF_WEIGHT = 0`). Les questions valides et hors sujet ont des scores de recherche qui se recouvrent : un filtre lexical ne peut pas les
séparer (compromis : refus seulement si correspondance très faible ; sinon résultats affichés avec un avertissement « correspondance faible »).

## Limites connues
* **Extractif = pas de raisonnement** : il renvoie des passages, il ne compare pas deux textes ni ne calcule.
* **Questions hors sujet reprenant des mots du corpus** (« gouverneur », « capital », « impôts ») ne sont pas toujours rejetées
  en mode extractif : le mode LLM doit les refuser, à mesurer.
* **Écart de vocabulaire** : « garantie maximale des dépôts » ne retrouve pas « plafond d'indemnisation » ; « emporter » ne retrouve pas « sortir/exporter ».
  La recherche compare des mots, pas des sens. Prochaine étape : embeddings multilingues + recherche hybride (voir plus bas).
* Corpus : textes français uniquement ; copies multiples (2021/2023) listées mais non départagées ; PDF OCR signalés « à vérifier ».
* Les numéros de textes mal parsés (ex. « Instruction n° 03 » seul) échouent à la recherche par référence (3/150 en test).

## Pour fiabiliser (à faire avec un juriste)
Étendre `agent_fr/eval/gold_seed.jsonl` (renseigner `validated_by`), viser ≥ 100 questions couvrant plusieurs thèmes (changes, LBC/FT,
prudentiel, paiements), et inclure des questions piégées (texte inexistant, texte remplacé, question avec date).

## Recherche sémantique : fait en phase 2
Embeddings multilingues locaux + BM25 + reranker local, sans appel externe : Recall@5 0,765 → 0,890 et MRR 0,638 → 0,770 (136 questions), exactitude bout en bout 0,589 → 0,857
(notation automatique ; jeux écrits par une IA, non validés par un juriste ; chiffres de bout en bout non aveugles). Voir [RETRIEVAL_PHASE2.md](RETRIEVAL_PHASE2.md), y compris ce qui n'a **pas** progressé
(jeu gold_v2 : 45/62 avant et après ; questions très lexicales ; arabe) et les prochaines étapes P0/P1/P2. Les mesures de ce fichier ci-dessus portent sur l'ancien moteur.

## Phase 3 : corpus final, statut juridique, benchmark indépendant
Corpus figé (1 085 documents, 11 112 chunks, OCR arabe de repli pour les couches texte corrompues, dates corrigées), module de statut juridique prouvé par le corpus (`agent_fr/legal_status.py` : ACTIVE, MODIFIED, REPLACED, ABROGATED, HISTORICAL, UNKNOWN ;
les séries annuelles ne s'abrogent pas entre elles), fournisseur LLM local par défaut, benchmark de 130 questions DEV / TEST. **Décision au 2026-10-07 : NO-GO** selon les critères pré-enregistrés (hallucination automatique 14,3 % en TEST, > 10 %),
**provisoire** : le benchmark est rédigé par une IA et n'a pas été validé par un juriste ; 0 erreur temporelle critique en TEST ; Recall@5 0,714 et réponse correcte 0,524 en TEST. Rapport complet : [RETRIEVAL_PHASE3.md](RETRIEVAL_PHASE3.md) ;
relecture humaine à faire : [HUMAN_REVIEW.md](HUMAN_REVIEW.md).

## Phase 4 : stabilisation du corpus (2026-10-07)
Corpus corrigé sans toucher au moteur : 0 identifiant de chunk dupliqué, 9 jumeaux FR/AR rattachés (3 conflits de dates laissés à un humain), relations vers le document français, dates arabes lues (mois collé à l'année), +229 articles arabes détectés,
38 « liens morts » = 19 anciens chemins déplacés (0 document perdu), valeurs numériques arabes suspectes marquées `OCR_UNCERTAIN` (jamais corrigées). `tessdata_best` mesuré sur un échantillon contrôlé : **non déployé** (gain de caractères +2,7 pts, valeurs juridiques équivalentes,
+44 % de temps, le « % » lu « 90 » n'est pas corrigé). Retrieval stable (DEV identique ; jeux historiques Recall@5 0,853 → 0,868). **NO-GO provisoire de la phase 3 maintenu** : aucune validation humaine n'existe encore ; TEST v1 inchangé ; TEST v2 non créé (protocole et verrou prêts).
Rapport : [RETRIEVAL_PHASE4.md](RETRIEVAL_PHASE4.md) ; mode d'emploi du juriste : [HUMAN_REVIEW.md](HUMAN_REVIEW.md).

## Phase 5 : gel technique (2026-10-07) — `PHASE_4_FROZEN`
Le système est gelé pour la validation juridique : manifeste complet (versions, configuration, modèles, embeddings, reranker, empreintes du corpus, de l'index, de TEST v1, des règles et du code) vérifiable par
`python -m agent_fr.eval.human.freeze_phase4 verify` ; reproductibilité contrôlée (vecteurs ré-encodés, corpus reconstruit octet pour octet, retrieval DEV rejoué, LLM rejoué 6/6). `tessdata_best` reste un candidat expérimental non déployé ; `OCR_UNCERTAIN` actif ;
H120, H129 et les trois conflits de dates FR/AR sont **laissés tels quels** pour le juriste. **Statut inchangé : NO-GO PROVISOIRE** (validation humaine absente, TEST v2 absent). Aucun TEST v2 n'est créé.
Documents : [PHASE_4_FROZEN.md](PHASE_4_FROZEN.md), [NOTE_AU_JURISTE.md](NOTE_AU_JURISTE.md), [HUMAN_REVIEW_QUICKSTART.md](HUMAN_REVIEW_QUICKSTART.md), [CAS_CRITIQUES_A_EXAMINER.md](CAS_CRITIQUES_A_EXAMINER.md), [ARBITRAGE_JUMEAUX_FR_AR.md](ARBITRAGE_JUMEAUX_FR_AR.md).

## Relecture humaine
`corpus/reports/legal_review_findings.md` (régénéré par `python agent_fr/eval/findings.py`) liste, pour un juriste : incohérences libellé/document,
copies en double dont les chiffres diffèrent, textes modifiés/abrogés, références à des textes absents du corpus.

## LLM local (Qwen3-4B-Instruct-2507, CPU)
`python -m agent_fr --local-llm "question"` (serveur : `llm_local\start_server.ps1`). Installation, mesures CPU/RAM, jeu aveugle et limites : voir `llm_local/README.md`.
Résumé : ~14 tok/s en génération sur i7-13700 sans GPU, ~3 Go de RAM, réponse d'agent en 20–90 s (médiane 31 s) ; l'interface web affiche d'abord les passages
puis la rédaction. Le LLM local refuse mieux les questions hors sujet que la recherche seule mais reste borné par la qualité de la recherche.
