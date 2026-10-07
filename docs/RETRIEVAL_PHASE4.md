# Phase 4 — Stabilisation du corpus et validation humaine

Principe : *ne pas chercher à rendre le benchmark meilleur, chercher à rendre le système plus vrai.* Cette phase corrige des défauts **objectifs** du corpus (identifiants, jumeaux FR/AR, dates, en-têtes arabes, liens, valeurs OCR suspectes),
prépare la validation humaine et le TEST v2, et ne touche ni au moteur de recherche ni à TEST v1.
Toutes les valeurs ci-dessous sont **mesurées** (fichiers sous `agent_fr/eval/results/`, tableaux régénérables par `python -m agent_fr.eval.human.make_tables4`, détail dans [tables_phase4.md](tables_phase4.md)).
Une cellule « non mesuré » signifie qu'aucune mesure n'existe : jamais d'estimation.

> **Avertissement permanent.** Le résultat de la phase 3 reste **NO-GO provisoire** et **n'est pas modifié** ici : la validation humaine (benchmark et réponses) n'a pas été faite — elle exige un juriste — donc aucune annotation humaine
> n'existe et le taux d'hallucination humaine ne peut pas encore être calculé. Les « relectures IA » citées sont explicitement **non humaines**. **La phase n'est donc pas terminée au sens de ses propres critères de sortie** (§ Critères de sortie).

## État de la phase en une page

| Critère de sortie | État | Preuve |
|---|---|---|
| Corpus : 0 identifiant de chunk dupliqué | **atteint** (107 occurrences en trop → 0) | `test_chunk_ids_are_unique_in_the_built_corpus`, `corpus_check_phase4` |
| Corpus : 0 relation FR/AR objectivement manquante | **atteint**, 3 exceptions documentées (conflits de dates, arbitrage humain) | §2 |
| Corpus : 0 lien mort critique | **atteint** (38 entrées = 19 URLs, toutes déplacées, 0 `BROKEN_SOURCE`) | §4 |
| OCR : chiffres, dates et références arabes critiques fiables ou marqués incertains | **partiellement atteint** : `tessdata_best` n'améliore pas les valeurs ; les valeurs suspectes sont marquées `OCR_UNCERTAIN` (80 chunks) là où un jumeau français permet de les comparer | §5–6 |
| Retrieval : `hybrid_rerank` stable après reconstruction | **atteint** (DEV identique ; jeux historiques Recall@5 0,853 → 0,868) | §8 |
| Validation : benchmark et réponses évalués par un humain compétent | **non atteint** (0 annotation) ; outillage prêt | §9–10 |
| TEST v2 indépendant prêt ou exécuté | **non atteint** ; protocole, gabarit, gel et verrou prêts ; aucune question écrite | §11 |

TEST v1 est strictement inchangé (11 fichiers vérifiés par empreinte avant et après la phase : `python -m agent_fr.eval.human.verify_frozen`). Aucune règle de recherche, de classement, de notation ni aucun seuil n'a été modifié.
**73 tests passent** (agent 25, pipeline 9, statut juridique 10, corpus phase 4 13, OCR numérique 7, annotations 4, protocole TEST v2 5).

## 1. Corrections du corpus (résumé)

Instantané : `D:\llm\snapshots\corpus_phase4` (SHA-256 des fichiers dans `SHA256SUMS.txt`) ; sauvegarde de l'état précédent : `D:\llm\snapshots\pre_phase4_backup` ; instantané de la phase 3 conservé tel quel.

| Mesure | Phase 3 | Phase 4 |
|---|---:|---:|
| Documents | 1 085 | 1 085 |
| Chunks (FR / AR / indéterminée) | 11 112 (7 789 / 3 317 / 6) | 11 320 (7 789 / 3 525 / 6) |
| Identifiants de chunks en double (occurrences en trop / identifiants / chunks) | 107 / 76 / 183 | **0 / 0 / 0** |
| Documents arabes / indéterminés sans jumeau de même `work_id` | 37 | 28 (3 conflits documentés ; 25 sans équivalent français de même type et numéro) |
| Articles arabes détectés (documents arabes sans aucun article) | 2 405 (35) | 2 634 (27) |
| Relations d'un texte FR dont le document cible est le jumeau arabe | 31 | 0 (642 relations entrantes, toutes vers le document FR) |
| Liens en échec (entrées / URLs uniques / sources cassées) | 38 / 19 / non classé | 38 → 19 / 19 / **0** |
| Chunks arabes `OCR_UNCERTAIN` | non mesuré | 80 (62 documents, 112 valeurs) |
| Anomalies BLOQUANT du contrôle d'intégrité | 0 (mais les doublons d'identifiants n'étaient que « INFO ») | 0 (un doublon est désormais BLOQUANT) |
| Textes distincts (`work_id`, toutes langues) | 679 | 670 (9 jumeaux rattachés) |

Les 11 314 vecteurs (FR + AR ; les 6 chunks de langue indéterminée ne sont pas indexés) ont été recalculés **incrémentalement** (332 chunks encodés, le reste réutilisé du cache par empreinte du texte) puis contrôlés : ordre identique au corpus, aucun NaN, normes = 1,
ré-encodage de 20 vecteurs tirés au hasard : cosinus 1,000000. Chaîne exécutée dans l'ordre demandé : documents → relations → chunks → identifiants → statut juridique → vecteurs → index.
Les chunks dont le texte est identique entre les deux versions : 10 986 / 11 320 ; les 334 textes nouveaux viennent surtout de la détection d'articles arabes (§3) et du renumérotage des annexes.

**Dates et identifiants modifiés (27 documents, tous relus)** : (a) 11 documents français perdent le suffixe de date de leur `work_id` (le jumeau arabe est désormais rattaché : un seul groupe) ; (b) 2 dates françaises fausses corrigées — INS-09-96 « 1995-12-23 » → 1996-12-19
(date du règlement cité → date du texte, lue dans « 19 décembre1996 ») et INS-27-91 « 1991-04-21 » → 1991-10-01 ; (c) 3 dates **retirées** parce qu'elles étaient celles d'un texte cité (NOT-02-24 et NOT-01-26 : 2016-09-01 ; NOT-04 : 2015-05-12) — « pas de date plutôt qu'une date fausse » ;
(d) 11 dates arabes ajoutées ou corrigées à partir du libellé du site (dont REG-08-04 : 2005 lu par l'OCR → 2008).
Vérification : le benchmark n'utilise que 3 des identifiants modifiés (REG-08-04-20081223, REG-25-03-20250414, NOT-02-24-20160901) ; une **copie dérivée** du seul DEV est remappée par empreinte de fichier (`remap_bench.py`), le benchmark d'origine n'est pas touché.

**Exceptions restantes, documentées** : 3 conflits de dates FR/AR (§2) ; 10 chunks à couche texte partiellement corrompue (lettres remplacées par des caractères de contrôle dans quelques mots ; 5 déjà connus, 5 révélés par un découpage plus fin) ;
2 « dates suspectes » qui sont des faux positifs (recueils de produits et services bancaires, datés « au 31 janvier 2022 » / « au 14 mai 2026 », numérotés 20-01) ; 20 documents sans date ; 16 références à des textes absents du corpus ;
28 documents arabes sans jumeau (dont 25 sans équivalent français : notes et communiqués arabes seulement, lois arabes isolées).

## 2. Problèmes FR/AR

Les 12 documents arabes de la phase 3 qui avaient un texte français de même type et même numéro sans lui être rattachés (tableau complet : [tables_phase4.md](tables_phase4.md), §B ; CSV : `agent_fr/eval/results/twins_phase4.csv`).

**Cause racine, objective** : l'analyse des dates arabes exigeait une espace entre le jour, le mois et l'année, alors que les libellés du site les collent (« 23 ديسمبر2008 », « 20 فبراير1991 », « 14غشت 1991 », « 14أفريل سنة 2025 ») et écrivent « الفاتح » pour le 1er.
Sans date lue, le texte arabe n'avait pas la date du français, donc pas le même `work_id` ; pour REG-08-04, la date manquante était remplacée par celle lue par l'OCR dans le corps (« 2005 » au lieu de 2008) : un faux texte du 23/12/2005 était créé.
Correction : analyse tolérante (jour, mois, année facultativement collés ; « الفاتح » = 1), **sans aucune similarité de contenu**.

| Résultat | Textes | Règle |
|---|---:|---|
| Rattachés par la date du libellé arabe, désormais lue (même type, même numéro, même date) | 7 : REG-06-02, REG-91-02, REG-08-04, REG-91-09, INS-08-21, LD-02-24, REG-25-03 | `R-TWIN-DATE` |
| Rattachés par jour-mois du libellé arabe (année absente) | 2 : REG-04-04, REG-92-10 | `R-TWIN-JOURMOIS` : un seul texte français de même type et numéro, jour et mois identiques, année de la date française présente dans le numéro ; la date est recopiée avec sa provenance |
| **Non rattachés : conflit de dates complètes** | 3 : REG-90-01, REG-02-01, REG-06-01 | jamais tranchés automatiquement |

Les trois conflits : REG-90-01 (arabe « 4 juin 1990 », français « 4 juillet 1990 » ; la date hégirienne imprimée dans le PDF arabe, 12 Dhou al-Hijja 1410, correspond au calendrier tabulaire à ± 2 jours au 4-6 juillet : la mention « juin » est probablement une coquille — **indice, pas preuve**),
REG-02-01 (20 contre 17 février 2002 ; date hégirienne arabe illisible), REG-06-01 (14 mai contre « 07 septembre » sans année ; peut-être deux textes distincts). Ils sont consignés avec leurs éléments pour et contre dans `boa_pipeline/twin_overrides.json` (champ `proposals`, `confirmed_by: null`) :
**seul un appariement confirmé par un humain (`confirmed`, `confirmed_by` renseigné) est appliqué**, test à l'appui (`test_twin_override_is_applied_only_when_confirmed_by_a_human`).

Autres corrections FR/AR : (1) une relation entrante (« modifié par… ») désignait parfois le **jumeau arabe** du texte modificateur (31 cas) parce que la déduplication gardait le premier document rencontré ; la remontée du texte modificateur cherchait alors un renvoi d'article français dans des chunks arabes
(question G038 : REG-24-05 modifiant REG-16-02). Le document source est maintenant le français. (2) Contrôle de cohérence : sur les 295 textes bilingues, **0** texte dont les relations FR et AR diffèrent.

## 3. Correction des identifiants de chunks

**Constat de la phase 3** : 76 identifiants portés par 183 chunks (groupes de 2, 3 ou 4). **Aucun doublon réel** : les 183 chunks ont tous un texte différent. Cause : `chunk.py` ne comparait un identifiant qu'aux 3 derniers chunks, donc un additif qui recommence à l'article 1,
ou des annexes de même numéro plus loin dans le même texte, passaient. Répartition mesurée :

| Cause | Identifiants |
|---|---:|
| Numérotation d'articles qui recommence dans le même texte (additif, partie 2) | 35 |
| Annexes dont le numéro a été lu « N » (« ANNEXE **N**° 1 ») ou « رقم » (= « numéro ») | 25 |
| Annexes de même numéro répétées dans un même texte | 16 |

**Correction** : (1) l'analyse d'en-tête d'annexe lit désormais le numéro (le « N° » majuscule et le mot « رقم » n'étaient pas reconnus : 77 chunks français et 42 chunks arabes portaient l'annexe « N » / « رقم ») ; (2) identifiant **unique par document, stable et déterministe** :
le premier chunk garde l'identifiant historique, un suivant reçoit `::u<indice de l'unité dans le document>` (puis `::d<n>` si besoin). Les identifiants non concernés ne changent pas : 10 662 des 11 005 identifiants distincts de la phase 3 sont inchangés ; 658 sont nouveaux et 343 disparus (11 320 identifiants distincts en phase 4), tous issus de ces deux corrections et du §3 bis.
**Tests** : unicité, stabilité (deux constructions identiques), déterminisme, identifiant historique conservé pour le premier, et garde-fou sur le corpus construit (`test_chunk_ids_are_unique_in_the_built_corpus`, qui échoue sur l'ancien corpus : 76 doublons). Le contrôle d'intégrité classe désormais un doublon **BLOQUANT**.

**§3 bis — en-têtes d'articles arabes collés (découverte de la phase 4, hors liste initiale).** Chercher pourquoi REG-25-07 n'avait « aucun article détecté » a révélé que « المادة8. — » (chiffre collé au mot) et les formes vocalisées (« المادَة », « المادّة ») n'étaient pas reconnues comme en-têtes :
**41 textes arabes** concernés, dont REG-20-01 (18 articles) et REG-26-03 (15) sans aucun article. Après correction : 69 documents arabes changent de nombre d'articles, **+229 articles** (2 405 → 2 634), documents sans article 35 → 27, chunks arabes +208. C'est une correction de l'**analyse de structure**
(le découpage en chunks, ses tailles et ses règles ne sont pas modifiés) ; elle est mesurée au §8 (la question arabe V041 sur REG-25-07 repasse au rang 1) et comporte un risque réel, signalé au §8 (H120).

## 4. Liens morts

« 38 liens morts » = **19 URLs uniques comptées deux fois** (étape de build + rapport de téléchargement). Les 19 sont d'anciens chemins `/pdf/<dossier>/<fichier>.pdf` que le site a migrés vers `/stoodroa/<année>/<mois>/<fichier>.pdf` ; le même fichier est **déjà dans le corpus** sous son URL officielle actuelle
(médiathèque du site) : **aucun document n'est perdu**.

| Question posée | Réponse mesurée |
|---|---|
| URL supprimée ? | non : l'ancien chemin répond HTTP 404 (vérifié en ligne le 2026-10-07, requêtes HEAD polies, 1 par seconde, robots.txt respecté) |
| URL déplacée ? | **oui, 19 / 19** : mêmes noms de fichiers sous `/stoodroa/…` ; les 22 URLs officielles de remplacement répondent HTTP 200 |
| Mauvaise URL extraite ? | non pour les 19 ; 4 intitulés de liens sont tronqués (« …r » + « elative à… ») : défaut d'extraction du libellé, pas de l'URL |
| Document absent ? | non : 0 `BROKEN_SOURCE` |
| Problème de normalisation ? | non |

Résolution **sans deviner d'URL** : un lien est « déplacé » (`MOVED_OFFICIAL`) seulement si un document du corpus porte le même nom de fichier sur une URL officielle déjà collectée **et** le même type + numéro (15), ou un intitulé tronqué contenu dans l'intitulé du document (1),
ou — confiance plus faible — le même nom de fichier et la même page de liste du site avec un intitulé tronqué (3 notes de 1998). Sinon `BROKEN_SOURCE`, l'information est conservée et rien n'est remplacé. L'ancienne URL est conservée comme `dead_source_urls` du document, **jamais** comme URL de référence.
`failed_documents.json` ne liste plus que les vrais échecs (0) ; `dead_links.json` et `dead_links_status.json` gardent tout. Test : `test_dead_links_are_deduplicated_and_resolved_only_from_official_urls_already_in_the_corpus`.
Les 19 anciens chemins sont **toujours listés par des pages du site** : le site lui-même expose des liens cassés.

## 5. Benchmark OCR arabe

`python -m agent_fr.eval.ocr_bench run | score` (sélection **gelée** avant la comparaison ; sorties en cache sous `results/ocr_bench/`). Le critère n'est pas le taux global de caractères mais les **valeurs juridiques** : chiffres, pourcentages, montants, dates, numéros d'articles, numéros de textes,
noms propres, termes juridiques (`boa_pipeline/ocr_entities.py`).

* **Jeu A, contrôles numériques** : 7 documents arabes à couche texte native saine (14 pages) rendus à 400 dpi puis passés à l'OCR ; la couche texte est la **vérité exacte**. 3 documents à couche texte partiellement corrompue ont été exclus (ce n'est pas une vérité). Limite : une page rendue proprement est plus facile qu'un scan réel ;
  les pourcentages ne sont pas mesurables sur ce jeu (le symbole « % » est isolé ou remplacé par un glyphe dans les couches texte).
* **Jeu B, scans problématiques** : 19 documents arabes OCR réels (les pires de l'audit — rappel des nombres < 50 % — et ceux du benchmark juridique), 81 pages ; la vérité des **valeurs** est le texte du **jumeau français** (même texte juridique) : seules les entités numériques sont comparées. Limite : une traduction peut écrire un nombre en toutes lettres.
  REG-25-07 (42 pages de tableaux de comptes, 987 nombres) domine les totaux : les chiffres sont donnés avec et sans lui, et en moyenne par document.
* **Aucune de ces vérités n'est une lecture humaine.** Noms propres et termes juridiques ne sont mesurés que sur le jeu A.

## 6. Comparaison OCR actuel / `tessdata_best`

`tessdata_best` n'a été testé **que sur cet échantillon contrôlé** (jeu A + jeu B), jamais déployé sur le corpus. Un seul fichier a été téléchargé : `ara.traineddata`, depuis `github.com/tesseract-ocr/tessdata_best` (branche `main`), 12 603 724 octets,
SHA-256 `ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896`, rangé sous `D:\llm\tessdata_best\` avec le modèle français rapide copié du Tesseract installé (provenance : `PROVENANCE.txt`) ; même rendu (400 dpi), même configuration, seul le modèle arabe change.

| Mesure | OCR actuel | `tessdata_best` | Écart |
|---|---:|---:|---:|
| Exactitude caractères (jeu A) | 0,821 | 0,847 | +0,027 |
| Chiffres / dates / numéros d'articles / numéros de textes (jeu A, rappel) | 0,960 / 0,934 / 0,914 / 0,976 | 0,954 / 0,934 / 0,886 / 0,976 | −0,006 / 0 / **−0,028** / 0 |
| Noms propres / termes juridiques (jeu A) | 0,636 / 0,986 | 0,727 / 0,986 | +0,091 (petit effectif) / 0 |
| Jeu B, chiffres : agrégé / hors REG-25-07 / moyenne par document | 0,337 / 0,581 / 0,738 | 0,428 / 0,617 / 0,756 | +0,091 / +0,036 / +0,018 |
| Jeu B, pourcentages / montants / dates (hors REG-25-07) | 0,071 / 0,062 / 0,330 | 0,107 / 0,188 / 0,350 | +0,036 / +0,126 / +0,020 |
| Jeu B, numéros d'articles / numéros de textes (moyenne par document) | 0,662 / 0,847 | 0,640 / 0,843 | −0,022 / −0,004 |
| Jeu B, nombres parasites (absents du jumeau français) | 8,9 % (13,9 % hors REG-25-07) | 7,4 % (13,2 %) | −1,5 pt (−0,7 pt) |
| Alertes `OCR_UNCERTAIN`, jeu B (unités signalées) | 13 / 84 | 15 / 88 | aucune réduction |
| Temps OCR par page | 1,51 s | 2,18 s | **+44 %** |

Valeurs critiques lues sur les documents du benchmark juridique (vérité = jumeau français) :

| Valeur attendue | OCR actuel | `tessdata_best` |
|---|---|---|
| INS-08-25 art. 2 : « 2,75 % » | `902.75` | `002.75` |
| INS-02-26 art. 2 : « 2,50 % » | `2,50 ١ %o` | valeur perdue |
| INS-01-26 art. 2 : « 1 % » | `د 1 %` | `ب 1 %` (lu correctement) |
| REG-97-04 art. 9 : « 600.000 » | `600.000` | `600.000` |

J'ai regardé le scan d'INS-08-25 : il porte bien « 2.75% » ; le symbole « % » placé devant la valeur est lu comme « 90 » ou « 00 ». Une seconde passe de reconnaissance restreinte aux chiffres sur le mot (psm 8, liste blanche) donne encore autre chose (« 962.75 ») : **ce n'est pas un réglage**, c'est une confusion intrinsèque du modèle pour cette police.

**Décision : `tessdata_best` n'est pas déployé.** Gain de caractères modeste (+2,7 points), valeurs juridiques équivalentes à ± 2 points avec des régressions (numéros d'articles, INS-02-26), le défaut critique du « % » n'est pas résolu, et le temps augmente de 44 %.
Un déploiement de masse (≈ 300 documents OCR) n'était pas justifié par la mesure. Le fichier reste disponible pour des tests. Le seul levier OCR restant qui exigerait une autorisation explicite est un autre moteur OCR (ressource externe non prévue) ; non fait.

## 7. `OCR_UNCERTAIN` : une valeur douteuse n'est jamais présentée comme certaine

Principe : **ne jamais normaliser silencieusement** une valeur OCR suspecte. Le texte OCR n'est pas modifié ; une alerte est ajoutée à l'article concerné, avec la raison et, quand elle existe, la valeur du jumeau français **à titre de comparaison** (jamais en remplacement).

| Règle (`boa_pipeline/ocr_check.py`) | Détecte |
|---|---|
| `R-OCR-ABSENT-JUMEAU` | taux / montant / décimale de l'arabe absent du français (« 902.75 » face à « 2,75 ») ; cause la plus fréquente identifiée : `R-OCR-PCT-GLYPH` (« % » lu « 90 », « 96 », « 00 » : 902.75, 960.25, 900.25, 00.25) |
| `R-OCR-MANQUANT` | taux / montant du français absent de l'arabe (valeur perdue) |
| `R-OCR-SYMBOLE` | « % » suivi d'une lettre parasite (« %o »), chiffre arabe-indien collé à une décimale (« 2,50 ١ ») |
| `R-OCR-TAUX` | pourcentage > 100 |

Gravité : **critique** (taux, montants, décimales, symbole) → alerte ; **information** (entier de ≥ 3 chiffres non corroboré : année, référence) → conservé pour la relecture, jamais d'avertissement. Les valeurs présentes ailleurs dans le texte français (défaut d'alignement des articles) ne sont pas signalées.
Les chiffres hégiriens et les nombres écrits en lettres ne sont pas comparés.

**Mesure du détecteur** (`agent_fr/eval/ocr_alert_audit.py`) : sur les articles arabes comparés au français, **couche texte native (aucune erreur d'OCR possible) : 0 alerte / 155** (plancher de faux positifs), mixtes 0 / 144, **OCR : 67 alertes / 2 043 (3,3 %)** ; 15 avec la cause « symbole % » identifiée.
Relecture **IA (non humaine)** de 24 alertes tirées au sort (graine 11, `ocr_alert_audit_ai_review.json`) : **17 erreurs d'OCR évidentes, 5 incertaines, 2 faux positifs** (différence de rédaction FR/AR, alignement d'articles) ; à confirmer par un humain.
Limite : seuls les textes arabes OCR **ayant un jumeau français** et des articles alignés sont comparables (2 043 articles) ; les autres ne reçoivent que les contrôles internes.

**Où l'alerte apparaît** : champs `ocr_uncertain` / `ocr_uncertain_tokens` du chunk, étiquette dans l'interface, et note déterministe dans la réponse (indépendante du LLM), plus forte si la réponse reprend la valeur : « ⚠ La réponse reprend la valeur douteuse 902.75. [S2] OCR_UNCERTAIN … vérifier dans le PDF officiel ».
Cas réel du DEV (H130, « taux directeur » en arabe) : le modèle écrit toujours « 902.75 % » (la notation automatique le compte faux), mais la réponse porte maintenant l'alerte ; sur les 78 réponses DEV, l'alerte apparaît dans **2** (H130 et H123), **aucune fausse alerte** sur les 76 autres.
Tests : `tests/test_ocr_numeric.py` — « 2,75 % », « 902.75 », « 1 % », « 2 000 000 DA », « 600 000 DA », « 1997 », « 2025 », « Article 25 », « Règlement 25-07 » ; année hégirienne et nombres en lettres jamais signalés.

## 8. Résultats DEV (régression) et comparaison phase 2 / phase 3 / phase 4

Seul le split DEV du benchmark humain a été exécuté (copie dérivée remappée ; LLM local Qwen3-4B, `hybrid_rerank`, aucun changement de règle). **TEST v1 n'a pas été ré-exécuté.**

| Mesure | Phase 3 DEV | Phase 4 DEV |
|---|---:|---:|
| Recall@1 / @3 / @5 / @10 / MRR | 0,641 / 0,797 / 0,828 / 0,859 / 0,723 | **identiques** |
| Exactitude temporelle@1 / juridique@1 | 0,667 / 0,881 | **identiques** |
| Réponse correcte (C1–C5) | 0,609 (39/64) | 0,625 (40/64) |
| Hallucination automatique | 0,125 (8/64) | 0,141 (9/64) |
| Erreur temporelle critique (règle automatique) | 2/57 | 1/57 |
| Refus corrects / clarifications | 9/9 / 5/5 | 9/9 / 5/5 |

**Le retrieval est stable** : 71 des 78 réponses sont identiques mot pour mot ; les 7 qui changent (types B, C, G et J) sont des questions dont le contexte donné au modèle a changé ; l'écart de réponse correcte (39 → 40 sur 64) est dans le bruit.

**Jeux historiques** (gold v2–v5, 136 questions, retrieval seul, corpus remappé par empreinte de fichier ; non strictement comparable à la phase 2) :

| `hybrid_rerank` | Phase 2 | Phase 3 | Phase 4 |
|---|---:|---:|---:|
| Recall@1 / @5 / MRR | 0,684 / 0,890 / 0,770 | 0,654 / 0,853 / 0,742 | **0,669 / 0,868 / 0,757** |
| Faux refus / refus corrects / clarifications | 1 / 28 sur 30 / 8 sur 8 | idem | idem |
| Questions arabes (13), Recall@5 | 10 | 9 | 10 |

Ce qui était demandé en particulier :

| Point suivi | Phase 2 → 3 → 4 (rang du bon passage) | Lecture |
|---|---|---|
| G038 (relation FR → jumeau arabe, REG-24-05 / REG-16-02) | 1 → absent → **1** | **corrigé** par le rattachement des relations au document français |
| V041 (REG-25-07, arabe) | 2 → absent → **1** | **corrigé** : les 9 articles arabes de REG-25-07 sont maintenant détectés |
| X019 / X026 / X028 (séries annuelles, règle de séries) | 1 → 8 → 8 ; 1 → 7 → 7 ; 4 → 7 → 7 | **inchangés, volontairement** : « en 2012 » y est lu comme l'exercice 2012 (la valeur de chaque période ne remplace pas la précédente) alors que le gold v5 attend l'année de signature ; aucune règle n'a été touchée pour ces questions isolées |
| W007 (« taux actuel des réserves obligatoires ») | 1 → 2 → 2 | inchangé |
| Valeurs numériques arabes (H129, H130, H123) | — | voir ci-dessous |

**Questions arabes du DEV et valeurs numériques.** (a) H130 : « 902.75 % » toujours produit, **désormais signalé** (§7). (b) H129 (taux actuel des réserves obligatoires en arabe) : le modèle répond « 3 % » d'après INS-02-23 art. 3 — **une valeur périmée présentée comme actuelle** (la valeur actuelle est dans INS-01-26) ;
la règle automatique ne le compte pas comme erreur temporelle critique (les versions interdites sont listées par article et l'article cité est le 3, pas le 2) : **la lecture IA en dénombre donc 2 réelles en DEV (H129, H130), pas 1** — écart de la règle de notation, documenté, la règle n'est pas modifiée. (c) H120 : la phase 3 refusait à tort ; la phase 4 répond **à partir d'un autre texte**
(INS-06-21, dont les articles arabes sont maintenant détectés) : un refus à tort est devenu une réponse hors sujet, une dégradation réelle liée à la correction de structure du §3 bis. Aucune règle n'a été ajustée pour cela ; c'est un risque connu à mesurer sur le prochain test indépendant.

## 9. Validation humaine : outillage prêt, rien n'est fait

Je n'ai pas qualité pour valider juridiquement : **0 annotation humaine**. Fichiers de la phase 3 inchangés (`benchmark_review.html`, `human_eval.html`) ; nouveaux paquets au schéma demandé, à côté : `review/benchmark_review_p4.html` (+ `.csv`, 130 questions) et `review/human_eval_p4.html` (les mêmes 60 réponses que la phase 3). Le rendu et l'enregistrement des réponses ont été testés dans le navigateur.

* **Benchmark** : question correcte ? source attendue ? article attendu ? réponse attendue ? date de référence ? + **CORRECT / INCORRECT / AMBIGU / QUESTION MAL FORMULÉE / SOURCE INCORRECTE / RÉPONSE ATTENDUE INCORRECTE**.
* **Réponses** : source ? article ? version juridique ? réponse ? citation ? suffisamment justifiée ? hallucination **non / juridique / factuelle / métadonnée interne / ne sait pas**.
* **Enregistrement sans interprétation** (`annotations.py`) : ajout seul dans `annotations/*.jsonl` (évaluateur, date, empreintes) ; export déjà intégré, valeur hors liste, identifiant inconnu ou évaluateur anonyme **refusés** ; le benchmark et les sorties de TEST v1 ne sont jamais réécrits ; aucune annotation n'est transformée en règle.
  L'ancienne commande `packs ingest-review` réécrivait le benchmark : elle **refuse maintenant** `benchmark_v1_draft.jsonl`.
* Une question mal conçue n'est **pas** comptée comme un échec du modèle (listée à part, jamais supprimée) ; pour une question de type G, « AMBIGU » est la bonne réponse.
* Mode d'emploi pour le juriste : [HUMAN_REVIEW.md](HUMAN_REVIEW.md).

## 10. Différences automatique / humain

**Non mesurables** : aucune évaluation humaine n'existe. Le recalcul (`annotations.py report`) est prêt et testé sur des fixtures : il présentera **séparément** hallucination juridique, hallucination factuelle, métadonnée interne, réponse correcte mais notation automatique incorrecte (et l'inverse),
compare le taux d'hallucination humaine au seuil pré-enregistré (≤ 5 % GO, ≤ 10 % CONDITIONAL GO, > 10 % NO-GO ; **seuils lus, jamais modifiés**, empreinte de `decision_criteria.md` vérifiée) et donne un intervalle de Wilson.
Les deux cas de TEST v1 où le modèle recopie la date de référence interne (H039, H053) et les deux de DEV (H041, H055) sont laissés à la qualification du juriste ; **la décision de la phase 3 n'est pas recalculée tant qu'ils ne le sont pas**.
Pour mémoire, la relecture IA de la phase 3 (non humaine) reste dans `ai_adjudication.json` ; elle n'a pas été modifiée.

## 11. TEST v2

**Non créé, non exécuté.** Il ne peut l'être qu'après la correction du corpus (fait), la décision OCR (faite), la validation humaine (**non faite**) et le gel des règles. `agent_fr/eval/human/test_v2.py` :

* **Questions rédigées par un humain** : gabarit `author-template` (à remplir par un juriste, sans consulter les réponses du système) ; `validate` refuse un auteur non humain, une question de DEV / TEST v1, un doublon, moins de 100 questions, un passage absent du corpus mot pour mot. **Je n'ai écrit aucune question** : elles ne seraient pas indépendantes.
* `status` vérifie les prérequis sur des fichiers (corpus sans BLOQUANT : oui ; OCR : oui ; validation humaine complète : **non** ; règles gelées : non) ; `freeze` refuse tant qu'un prérequis manque, sans `--confirm-no-tuning`, ou si le fichier n'est pas valide ; il fige les questions, **tout le code qui influence les résultats**, le corpus, les vecteurs,
  les modèles (SHA-256), les critères de décision, la configuration et les versions.
* `run` refuse sans manifeste, si le code, le corpus ou les questions ont changé depuis le gel, ou si TEST v2 a déjà été exécuté : un **verrou est écrit avant l'exécution et jamais supprimé** ; les sorties passent en lecture seule avec leur empreinte. Une correction ultérieure se fait par **re-notation**, jamais par ré-exécution.
* 5 tests (dont : le verrou existe au moment de l'exécution ; une seconde exécution est refusée ; un fichier de TEST v2 absent ou modifié est refusé).

## 12. Décision finale

**Décision de la phase 3 maintenue : NO-GO provisoire**, sans modification ni réinterprétation. Rien dans cette phase ne la change : les corrections de corpus sont réelles (corpus plus vrai, retrieval stable) mais ne remplacent ni la validation humaine ni un test indépendant,
et le seul critère qui déclenchait le NO-GO — l'hallucination — dépend d'une qualification humaine encore absente.
Le seuil de 10 % n'est pas modifié ; les cas difficiles (H120 devenu réponse hors sujet, H129 valeur périmée, H130 valeur OCR) sont conservés et documentés.
La phase 4 **n'est pas terminée** : restent la validation humaine du benchmark et des réponses, puis la rédaction, le gel et l'exécution de TEST v2 par un juriste.

## 13. Limites restantes

1. **Aucune validation humaine** : benchmark (130 questions), 60 réponses, statuts attendus, qualification des « métadonnées internes » — tout dépend d'un juriste. Les relectures IA (causes d'échec, 24 alertes OCR) ne sont pas une validation.
2. **L'OCR arabe reste imparfait** : le symbole « % » placé devant une valeur est lu comme des chiffres ; `tessdata_best` ne le corrige pas. Les valeurs sont **signalées** (`OCR_UNCERTAIN`), pas corrigées ; sans jumeau français ou sans article aligné, seule une partie des contrôles s'applique ;
   les entiers (années, références) non corroborés ne déclenchent pas d'alerte. 10 chunks arabes ont une couche texte partiellement corrompue.
3. **Trois jumeaux FR/AR en conflit de dates** (REG-90-01, REG-02-01, REG-06-01) attendent un arbitrage ; 25 documents arabes n'ont pas d'équivalent français.
4. **Règle de notation et valeurs périmées** : les « versions interdites » sont listées par article ; une valeur périmée citée à un autre article du même texte (H129) n'est pas comptée comme erreur temporelle critique. Écart documenté, règle inchangée.
5. **Correction de structure arabe (§3 bis)** : +229 articles détectés améliore le retrieval arabe (V041) mais a transformé un refus à tort en réponse hors sujet (H120) ; à mesurer sur un test indépendant.
6. **Séries annuelles** : la lecture « en N = exercice N » (3 questions du gold v5) est un choix documenté ; le juriste doit arbitrer la lecture du gold.
7. **Corpus** : 20 documents sans date, 16 références à des textes absents, 337 textes de statut UNKNOWN ; le corpus reste « ce que le site expose ».
8. TEST v1 est consommé : toute mesure nouvelle doit passer par TEST v2. Les résultats DEV ne sont pas aveugles (DEV a servi à régler la phase 3).

## Journal des modifications de la phase 4

| Fichier | Changement | Pourquoi / mesure |
|---|---|---|
| `boa_pipeline/classify.py` | dates arabes tolérantes (jour/mois/année collés, « الفاتح ») ; mois collé à l'année en français ; « n° » insensible à la casse pour reconnaître le numéro propre | 9 jumeaux ; 2 dates fausses corrigées ; 3 dates retirées (§1–2) |
| `boa_pipeline/build.py` | pas de date quand le premier « type n° » du texte est un texte cité ; liens morts dédoublonnés et résolus ; contrôle `OCR_UNCERTAIN` | §1, §4, §7 |
| `boa_pipeline/relations.py` | `pair_twins`, `apply_twin_overrides` ; relation entrante vers le document français | §2 |
| `boa_pipeline/chunk.py`, `structure.py` | identifiants uniques ; numéro d'annexe ; en-têtes d'articles arabes collés / vocalisés | §3 |
| `boa_pipeline/deadlinks.py`, `deadlinks_check.py`, `ocr_entities.py`, `ocr_check.py`, `twin_overrides.json` | nouveaux | §2, §4, §7 |
| `agent_fr/answer.py`, `app.py` | alerte `OCR_UNCERTAIN` déterministe (réponse et interface) ; aucun changement de prompt ni de classement | §7 |
| `agent_fr/eval/` | `ocr_bench.py`, `ocr_alert_audit.py`, `regression_phase4.py`, `human/{verify_frozen,remap_bench,annotations,packs_p4,test_v2,make_tables4}.py`, `human/corpus_check.py` durci | §5–11 |
| `tests/` | `test_phase4_corpus.py`, `test_ocr_numeric.py`, `test_human_annotations.py`, `test_test_v2_protocol.py` | 29 nouveaux tests |

**Non modifiés** : modèle d'embeddings, reranker, poids de fusion, seuils de refus, logique de classement, règles de notation (`bench.py`, `score.py`), critères de décision, TEST v1 (questions, réponses attendues, sorties, notes).

## Reproduire

```
python -m agent_fr.eval.human.verify_frozen                      # TEST v1 intact
python -m boa_pipeline scope && python -m boa_pipeline build && python -m boa_pipeline status
python -m agent_fr.eval.human.snapshot_corpus --name corpus_phase4       # copie + vecteurs incrémentaux
python -m boa_pipeline.deadlinks_check                            # requêtes HEAD polies
python -m agent_fr.eval.human.corpus_check --corpus D:/llm/snapshots/corpus_phase4 --out agent_fr/eval/results/corpus_check_phase4
python -m agent_fr.eval.ocr_bench run --engines actuel tessdata_best && python -m agent_fr.eval.ocr_bench score
python -m agent_fr.eval.ocr_alert_audit --n 24
python -m agent_fr.eval.human.remap_bench --old D:/llm/snapshots/corpus_phase3_final --new D:/llm/snapshots/corpus_phase4 --split DEV --out agent_fr/eval/human/benchmark_dev_phase4.jsonl
set AGENT_CORPUS_DIR=D:/llm/snapshots/corpus_phase4
python -m agent_fr.eval.regression_phase4 --pipelines hybrid_rerank legacy
python -m agent_fr.eval.human.run_bench --bench agent_fr/eval/human/benchmark_dev_phase4.jsonl --split DEV --pipeline hybrid_rerank --tag dev_phase4
python -m agent_fr.eval.human.make_tables4 > docs/tables_phase4.md
for t in test_agent test_pipeline test_legal_status test_phase4_corpus test_ocr_numeric test_human_annotations test_test_v2_protocol: python tests/<t>.py   (sans AGENT_CORPUS_DIR)
```
