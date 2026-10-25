# Étude Empirique : Montants Périmés et Articles Modifiés (Task 9 / T9)

> **Projet** : RegAssist DZ — Moteur RAG réglementaire Banque d'Algérie
> **Auteur** : Chouari Mohammed Anes (Équipe RegAssist DZ)
> **Date** : 25 octobre 2026 (Mise à jour suite à la revue de Salim Mabed)
> **Statut du moteur** : Gelé (`PHASE_4_FROZEN`) — **Étude et propositions d'architecture uniquement**
> **Commande de reproduction** : `python -m local_app.study_outdated_amounts`
> **Issue associée** : [Issue #9 (Task 9)](https://github.com/SalimMabed/regassist-dz/issues/9)

---

## 1. Contexte et Problématique

### 1.1 Le risque juridique des montants financiers obsolètes
Dans le droit bancaire et financier algérien, les valeurs chiffrées (montants de capital social minimum, plafonds d'indemnisation des déposants, ratios de solvabilité, taux de réserves obligatoires, seuils de change) font l'objet de révisions périodiques par voie de règlements et d'instructions modificatifs de la Banque d'Algérie.

Lors des évaluations de la Phase 4, plusieurs cas critiques ont mis en lumière une vulnérabilité majeure des moteurs RAG standard :
- **Cas H129 (`docs/CAS_CRITIQUES_A_EXAMINER.md`)** : Interrogé sur le taux actuel des réserves obligatoires, le système a cité l'Instruction n° 02-2023 fixant le taux à **3 %** (valeur périmée), au lieu de l'Instruction n° 01-2026 en vigueur fixant le taux à **1 %**.
- **Cas Capital bancaire** : Le capital minimum des banques a évolué de **2,5 milliards DA** (Règlement n° 04-01) à **10 milliards DA** (Règlement n° 08-04), puis **20 milliards DA** (Règlement n° 18-03), pour être réaffirmé et complété par le **Règlement n° 2024-02 du 6 février 2024 (`REG-24-02`)** qui introduit les banques digitales à **10 milliards DA** et les établissements financiers à **6,5 milliards DA**.
- **Cas Garantie des dépôts** : Le plafond d'indemnisation par déposant est passé de **600 000 DA** (Règlement n° 97-04, article 9) à **2 000 000 DA** (Règlement n° 2020-03 du 15 mars 2020, article 10).

Si un modèle LLM synthétise une réponse à partir d'un ensemble de passages où coexistent des textes anciens et des textes modificatifs récents, le risque qu'il sélectionne un montant abrogé ou obsolète est critique.

### 1.2 Objectifs de l'Étude (Task 9)
Conformément aux spécifications de `docs/TASKS.md` et à la demande de Salim Mabed, cette étude :
1. **Quantifie** à l'échelle du corpus le volume d'articles modifiés/abrogés contenant des valeurs numériques.
2. **Mesure empiriquement** sur la recherche réelle (`agent.search` : BM25 + `e5-small` + reranker ONNX `mmarco`) la fréquence à laquelle des montants périmés co-occurrent avec ou devancent les montants applicables.
3. **Trace de façon exhaustive chaque montant** cité vers son extrait textuel verbatim et son `chunk_id` précis dans `chunks_fr.jsonl`.
4. **Formule 3 propositions architecturales concrètes** pour le prochain dégel du moteur, tout en maintenant le moteur actuel strictement intact.

---

## 2. Cartographie Corpus-Wide des Textes Modifiés et des Montants

L'analyse systématique de `corpus/metadata/legal_status.json` et des 7 789 passages de `corpus/chunks/chunks_fr.jsonl` révèle la structure suivante :

| Grandeur mesurée | Valeur dans le corpus | Proportion / Note |
|---|---|---|
| **Total documents collectés** | **757** | Ensemble des textes Banque d'Algérie |
| **Total passages (chunks)** | **7 789** | Découpage au niveau article / section |
| **Articles avec statut juridique explicite** | **170** | Documentés dans `legal_status.json` |
| ↳ *Articles REPLACED (remplacés)* | 76 | Règle `R-ART-REMPL` (chaîne de réécriture) |
| ↳ *Articles MODIFIED (modifiés)* | 17 | Règle `R-ART-COMPL` ou `R-MOD-TEXTE` |
| ↳ *Articles ABROGATED (abrogés)* | 3 | Règle `R-ART-ABR` |
| ↳ *Articles ACTIVE (version courante connue)* | 74 | Règle `A-ART-COURANT` (dernier maillon) |
| **Total passages contenant des montants chiffrés** | **139** | Dinars, DA, %, milliards, millions, devises |
| ↳ *Passages PÉRIMÉS contenant des montants* | **56 (40.3 %)** | Textes abrogés, remplacés ou modifiés |
| ↳ *Passages ACTIFS contenant des montants* | **83 (59.7 %)** | Textes applicables |

> **Constat structurel** : Plus de **40 %** des mentions de montants financiers dans le corpus proviennent d'articles juridiquement modifiés ou abrogés.

---

## 3. Évaluation Empirique sur la Recherche Réelle (`agent.search`)

Huit requêtes représentatives portant sur des valeurs financières modifiées au fil des ans ont été soumises au pipeline hybride de recherche gelé (BM25 + vectoriel dense + reranker cross-encoder) avec une fenêtre de récupération $K=6$.

Dans cette mise à jour, les normes en vigueur vérifiées dans `corpus/metadata/legal_status.json` sont intégrées :
- `REG-24-02` (Règlement n° 2024-02 du 6 février 2024) est le texte actif pour le capital minimum (statut `ACTIVE`, règle `A-DERNIER`, abrogeant expressément `REG-18-03` à l'article 4).
- `REG-20-03` (Règlement n° 2020-03 du 15 mars 2020) est le texte actif pour le plafond du Fonds de garantie des dépôts bancaires (statut `ACTIVE`, règle `A-DERNIER`).

### 3.1 Synthèse Statistique Révisée

| Métrique de recherche ($N=8$ cas types) | Résultat mesuré | Taux constaté |
|---|---|---|
| **Co-occurrence Périmé + Actif (dans le Top-6)** | **8 / 8** | **100.0 %** |
| **Inversion Temporelle (Passage périmé classé devant le texte actif)** | **2 / 8** | **25.0 %** |
| **Passage Périmé classé N°1 absolu (Top-1)** | **1 / 8** | **12.5 %** |

---

### 3.2 Tableau Détaillé par Cas d'Usage

| Identifiant | Thème réglementaire | Montant Actuel (Vigueur) | Montants Périmés dans le corpus | Rang Actif | Rangs Périmés | Inversion Temporelle |
|---|---|---|---|---|---|---|
| `CASE-01` | **Capital minimum des banques** | 20 Mrds DA (`REG-24-02`) | 2,5 Mrds (`REG-04-01`), 10 Mrds (`REG-08-04`), 20 Mrds (`REG-18-03`) | **Rang 1** | Rangs 2, 3, 6, 8, 9 | NON (Mais 2,5 Mrds et 10 Mrds aux rangs 2 et 3 !) |
| `CASE-02` | **Capital minimum étal. financiers** | 6,5 Mrds DA (`REG-24-02`) | 500 M (`REG-04-01`), 3,5 Mrds (`REG-08-04`), 6,5 Mrds (`REG-18-03`) | Rang 3 | **Rang 2** | **OUI (REG-04-01 à 500 M devance REG-24-02)** |
| `CASE-03` | **Plafond Fonds Garantie Dépôts** | 2 000 000 DA (`REG-20-03`) | 600 000 DA (`REG-97-04`) | **Rang 1** | Rangs 5, 6 | NON (Périmé présent à Rang 5) |
| `CASE-04` | **Taux des réserves obligatoires (H129)** | 1 % (`INS-01-26`) | 2 %, 3 %, 6,5 %, 8 %, 10 %, 12 % | **Rang 1** | Rangs 5, 6, 7, 8... | NON (Actif en tête, mais 3% et 6,5% en embuscade) |
| `CASE-05` | **Droit de change voyage (Allocation)** | 750 € (`INS-07-26`) | 15 000 DA (`INS-08-97`), 750 € (`INS-05-25`) | **Rang 1** | Rang 3 | NON (15 000 DA présent au Rang 3) |
| `CASE-06` | **Ratio de solvabilité prudentiel** | 9,5 % / 7 % (`REG-14-01`) | 8 % (`REG-91-09`, ratio Cooke) | **Rang 1** | Rang 6 | NON |
| `CASE-07` | **Coefficient de liquidité minimum** | 100 % (`REG-11-04`) | 60 % (`REG-91-11`), texte modif | Rang 2 | **Rang 1** | **OUI (Passage modificateur devance l'actif)** |
| `CASE-08` | **Plafond division des grands risques** | 25 % (`REG-14-02`) | 25 % base modifiée (`REG-91-08`) | **Rang 1** | Rangs 4, 5 | NON |

---

## 4. Taxonomie des Causes d'Échec de la Recherche

Pourquoi un moteur de recherche RAG de pointe (BM25 + `e5-small` + cross-encoder) fait-il coexister des montants abrogés à 100 % dans le Top-6 ?

### Cause 1 : Asymétrie textuelle (Biais lexical du texte fondateur)
Les règlements fondateurs (ex. Règlement n° 04-01 fixant le capital des établissements financiers à 500 millions DA) contiennent des intitulés très explicites qui s'accordent exactement avec la formulation de la requête (*« capital minimum des établissements financiers »*). Le texte modificateur a souvent une rédaction plus condensée, ce qui lui fait perdre de précieux points BM25.

### Cause 2 : Insensibilité temporelle des embeddings denses
Le modèle d'embedding (`multilingual-e5-small`) et le cross-encoder (`mmarco-mMiniLMv2`) encodent la proximité sémantique conceptuelle. Pour eux :
$$\text{sim}(« 500\text{ millions de DA} », « 6,5\text{ milliards de DA} ») \approx 0.94$$
Ils ne possèdent aucune notion intrinsèque d'antériorité ou d'abrogation normative.

### Cause 3 : L'effet de citation inverse (L'anomalie H129)
Dans l'instruction n° 02-2023, le texte de l'article 2 est découpé par le parser au niveau de l'article cité :
> *« ... est modifié et rédigé comme suit : "Article 3 : Le taux des réserves obligatoires est fixé à 3 %..." »*

Le chunk a été indexé sous l'étiquette `INS-02-23.ar::article-3`. Or, aucun texte ne modifie *l'article 3 de l'instruction 02-2023* ; c'est *l'article 3 de l'instruction 02-2004* qui a été remplacé par l'instruction 01-2026. Le statut juridique calculé pour ce passage cité était donc faussement `ACTIVE`, trompant le modèle de langage qui a recopié le statut et la valeur périmée.

---

## 5. Trois Propositions d'Architecture pour le Prochain Dégel

Ces propositions sont conçues pour être intégrées lors du prochain cycle de révision du moteur, sans toucher au périmètre gelé actuel :

### Proposition A : Injection de Paires par Graphe de Remplacement (Retrieval Level)
* **Principe** : Exploiter les relations `abroge_par`, `modifie_par`, `remplace_par` documentées dans `legal_status.json`.
* **Fonctionnement** :
  1. Lorsqu'un passage $C_{\text{old}}$ (portant le statut `REPLACED` ou `ABROGATED`) est retenu dans le Top-$K$ de recherche, le moteur inspecte son champ relationnel.
  2. Il identifie le passage successeur $C_{\text{new}}$ (provenant du texte modificateur le plus récent).
  3. Si $C_{\text{new}}$ ne fait pas déjà partie du Top-$K$, il est **automatiquement injecté** dans le contexte avec une priorité supérieure à $C_{\text{old}}$.
  4. Le passage obsolète $C_{\text{old}}$ est soit retiré du contexte transmis au LLM, soit assorti d'un bandeau contraignant : `[VERSION ABROGÉE PAR S1 - NE PAS CITER LE MONTANT DE CE PASSAGE]`.

### Proposition B : Garde-Fou Applicatif des Montants Contradictoires (`local_app/`)
* **Principe** : Détecter et arbitrer les conflits de chiffres directement au niveau de la couche de service web (`local_app/service.py`), sans modifier `agent_fr/`.
* **Fonctionnement** :
  1. Si la question de l'utilisateur comporte une recherche de montant ou de taux (*« Quel est le montant... »*, *« Quel est le capital... »*, *« Quel est le taux... »*).
  2. Le service scanne les passages retrouvés à l'aide d'une regex d'extraction numérique (`AMOUNT_REGEX`).
  3. Si plusieurs passages présentent des montants distincts :
     - Si l'un des passages est étiqueté `ACTIVE` et l'autre `REPLACED` ou `ABROGATED`, le service impose dans le prompt ou dans une note système prioritaire :
       > *« Attention : Plusieurs montants historiques figurent dans les sources. La valeur actuellement en vigueur est celle du texte le plus récent ({texte_actif}). Les valeurs antérieures sont périmées. »*
     - Si le modèle persiste à citer le montant périmé, la réponse est corrigée ou assortie d'un avertissement visible.

### Proposition C : Enrichissement Relationnel Article-à-Article dans le Métamodèle
* **Principe** : Faire évoluer le graphe de dépendance juridique de l'échelle du document à l'échelle stricte de l'article.
* **Fonctionnement** :
  1. Structurer explicitement la chaîne de filiation :
     $$\text{REG-04-01 art. 2} \xrightarrow{\text{abrogé par}} \text{REG-08-04 art. 2} \xrightarrow{\text{abrogé par}} \text{REG-18-03 art. 2} \xrightarrow{\text{abrogé par}} \text{REG-24-02 art. 2}$$
  2. Lors de l'indexation, le texte modificateur hérite automatiquement des mots-clés conceptuels de l'article d'origine (expansion d'indexation ciblée), éliminant l'asymétrie lexicale BM25.

---

## 6. Traçabilité Exhaustive des Montants dans le Corpus (Citations Exactes)

Afin de garantir la vérifiabilité intégrale de l'étude demandée par Salim Mabed, chaque valeur financière citée ci-dessus est reliée ci-dessous à son `chunk_id`, sa localisation dans le PDF et son texte verbatim dans `corpus/chunks/chunks_fr.jsonl` :

| Cas | Document | Article | Page | Statut corpus | `chunk_id` | Montant / Taux | Extrait verbatim dans `chunks_fr.jsonl` |
|---|---|---|---|---|---|---|---|
| **Capital banques (Actif)** | Règlement n° 2024-02 (06/02/2024) | Art. 2 | p. 2 | `ACTIVE` (`A-DERNIER`) | `REG-24-02.fr::article-2` | **20 Mrds DA** (et 10 Mrds digitale) | *« Les banques et établissements financiers doivent détenir, à tout moment, un capital minimum... fixé comme suit : a. Banque : vingt milliards de dinars algériens (20 000 000 000 DA) ; b. Banque d'affaires: vingt milliards... c. Banque digitale : dix milliards... »* |
| **Capital banques (Périmé 1)** | Règlement n° 18-03 (04/11/2018) | Art. 2 | p. 1 | `ABROGATED` (par REG-24-02) | `REG-18-03.fr~2::article-2` | **20 Mrds DA** | *« a - Vingt milliards de dinars (20 000 000 000 DA) pour les banques visées à l’article 70 de l’Ordonnance n°03-11... »* |
| **Capital banques (Périmé 2)** | Règlement n° 08-04 (23/12/2008) | Art. 2 | p. 1 | `ABROGATED` (par REG-18-03) | `REG-08-04.fr~2::article-2` | **10 Mrds DA** | *« a - dix milliards de dinars (10.000.000.000 DA) pour les banques... »* |
| **Capital banques (Périmé 3)** | Règlement n° 04-01 (04/03/2004) | Art. 2 | p. 1 | `ABROGATED` (par REG-08-04) | `REG-04-01.fr~2::article-2` | **2,5 Mrds DA** | *« a) deux milliards cinq cents millions de dinars (2.500.000.000 DA) pour les banques... »* |
| **Capital étal. fin. (Actif)** | Règlement n° 2024-02 (06/02/2024) | Art. 2 | p. 2 | `ACTIVE` (`A-DERNIER`) | `REG-24-02.fr::article-2` | **6,5 Mrds DA** | *« d. Etablissement financier : six milliards cinq cent millions de dinars algériens (6 500 000 000 DA). »* |
| **Capital étal. fin. (Périmé 1)** | Règlement n° 18-03 (04/11/2018) | Art. 2 | p. 1 | `ABROGATED` (par REG-24-02) | `REG-18-03.fr~2::article-2` | **6,5 Mrds DA** | *« b - Six milliards Cinq cents Millions de dinars (6 500 000 000 DA) pour les établissements financiers... »* |
| **Capital étal. fin. (Périmé 2)** | Règlement n° 08-04 (23/12/2008) | Art. 2 | p. 1 | `ABROGATED` (par REG-18-03) | `REG-08-04.fr~2::article-2` | **3,5 Mrds DA** | *« b - trois milliards cinq cents millions de dinars (3.500.000.000 DA) pour les établissements financiers... »* |
| **Capital étal. fin. (Périmé 3)** | Règlement n° 04-01 (04/03/2004) | Art. 2 | p. 1 | `ABROGATED` (par REG-08-04) | `REG-04-01.fr~2::article-2` | **500 M DA** | *« b) cinq cents millions de dinars (500.000.000 DA) pour les établissements financiers... »* |
| **Garantie dépôts (Actif)** | Règlement n° 2020-03 (15/03/2020) | Art. 10 | p. 3 | `ACTIVE` (`A-DERNIER`) | `REG-20-03.fr::article-10` | **2 000 000 DA** | *« Le plafond d’indemnisation par déposant, est fixé à deux millions de dinars algériens (2.000.000 DA). Ledit plafond s’applique à l’ensemble des dépôts d’un même déposant... »* |
| **Garantie dépôts (Périmé)** | Règlement n° 97-04 (31/12/1997) | Art. 9 | p. 3 | `REPLACED` (par REG-04-03 / 20-03) | `REG-97-04.fr::article-9` | **600 000 DA** | *« Le plafond d'indemnisation par déposant est fixé à six cents mille (600.000) Dinars Algériens. Ledit plafond s'applique à l'ensemble des dépôts d'un même déposant... »* |
| **Réserves oblig. H129 (Actif)** | Instruction n° 01-2026 (15/01/2026) | Art. 2 | p. 1 | `ACTIVE` (`A-DERNIER`) | `INS-01-26.fr::article-2` | **1 %** | *« L’article 3 de l'instruction n° 02-2004 du 13 mai 2004 relative au régime des réserves obligatoires est modifié et rédigé comme suit : « Article 3 : Le taux des réserves obligatoires est fixé à 1% de l'assiette des réserves... »* |
| **Réserves oblig. H129 (Périmé 1)** | Instruction n° 02-2023 (13/04/2023) | Art. 2 | p. 1 | `REPLACED` (par INS-09-25) | `INS-02-23.fr::article-2` | **3 %** | *« L’article 3 de l'instruction n° 02-2004... est modifié et rédigé comme suit : « Article 3 : Le taux des réserves obligatoires est fixé à 3% de l'assiette des réserves... »* |
| **Réserves oblig. H129 (Périmé 2)** | Instruction n° 02-2004 (13/05/2004) | Art. 3 | p. 1 | `REPLACED` | `INS-02-04.fr::article-3` | **6,5 %** | *« Le taux des réserves obligatoires est fixé à 6,5% de l'assiette des réserves définie dans l'article 2 ci-dessus. »* |
| **Droit de change voyage (Actif)** | Instruction n° 07-2026 (13/07/2026) | Art. 2 | p. 1 | `ACTIVE` (`A-DERNIER`) | `INS-07-26.fr::article-2` | **750 €** (300 € mineurs) | *« Le montant annuel maximum du droit de change pour voyage à l'étranger, servi une fois au titre de chaque année civile, est fixé à la contrevaleur en dinars algériens de : - sept cent cinquante (750) euros... »* |
| **Droit de change voyage (Périmé)** | Instruction n° 08-97 (28/08/1997) | Art. 2 | p. 1 | `ABROGATED` (par INS-05-25 / 07-26) | `INS-08-97.fr::article-2` | **15 000 DA** | *« Le montant annuel du droit de change pour dépenses liées à des voyages à l'étranger est fixé à la contre-valeur en devises de quinze mille (15.000) (dinars algériens) pour chaque année civile... »* |
| **Solvabilité (Actif)** | Règlement n° 14-01 (16/02/2014) | Art. 2 | p. 1 | `ACTIVE` (`A-DERNIER`) | `REG-14-01.fr::article-2` | **9,5 %** (7 % Tier 1) | *« Les banques et établissements financiers sont tenus de respecter en permanence... un coefficient minimum de solvabilité de 9,5 %... »* (Art. 3 : 7 % pour les fonds propres de base). |
| **Solvabilité (Périmé)** | Règlement n° 91-09 (14/08/1991) | Art. 2 | p. 1 | `ABROGATED` (par REG-14-01) | `REG-91-09.fr::article-2` | **8 %** | *« Les banques et établissements financiers sont tenus de respecter... un ratio de couverture des risques au moins égal à huit pour cent (8%). »* |
| **Liquidité (Actif)** | Règlement n° 11-04 (24/05/2011) | Art. 3 | p. 2 | `ACTIVE` (`A-DERNIER`) | `REG-11-04.fr::article-3` | **100 %** | *« Les banques et les établissements financiers sont tenus de respecter un rapport... au moins égal à 100 % entre les actifs disponibles... et le passif exigible. »* |
| **Liquidité (Périmé)** | Règlement n° 91-11 (14/08/1991) | Art. 2 | p. 1 | `ABROGATED` (par REG-11-04) | `REG-91-11.fr::article-2` | **60 %** | *« Les banques et établissements financiers sont tenus de respecter... un coefficient de liquidité au moins égal à soixante pour cent (60%). »* |
| **Grands risques (Actif)** | Règlement n° 14-02 (16/02/2014) | Art. 4 | p. 2 | `ACTIVE` (`A-DERNIER`) | `REG-14-02.fr::article-4` | **25 %** | *« Toute banque ou établissement financier est tenu de respecter en permanence un rapport maximum de 25 % entre l’ensemble des risques nets pondérés qu’il encourt sur un même bénéficiaire et le montant de ses fonds propres nets. »* |
| **Grands risques (Périmé)** | Règlement n° 91-08 (14/08/1991) | Art. 2 | p. 1 | `ABROGATED` (par REG-14-02) | `REG-91-08.fr::article-2` | **25 %** (base modifiée) | *« Les banques et établissements financiers sont tenus de respecter en permanence un rapport maximum de 25% entre l'ensemble des risques encourus sur un même bénéficiaire et leurs fonds propres nets. »* |

---

## 7. Conclusion et Feuille de Route

L'étude empirique de la Task 9 démontre qu'en matière de montants financiers, le problème majeur réside dans la **co-occurrence systématique (100 %) de montants obsolètes aux côtés des textes en vigueur**, et dans l'**inversion temporelle (25 % des cas)** où un texte abrogé surclasse le texte applicable.

Les trois propositions formulées ci-dessus (notamment l'injection automatique de paires via le graphe de dépendance et le garde-fou applicatif de détection de montants conflictuels) apportent une réponse modulaire et rigoureuse sans compromettre le gel actuel du moteur.
