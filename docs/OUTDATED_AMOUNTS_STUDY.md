# Étude Empirique : Montants Périmés et Articles Modifiés (Task 9 / T9)

> **Projet** : RegAssist DZ — Moteur RAG réglementaire Banque d'Algérie
> **Auteur** : Anes Mabed / Équipe RegAssist
> **Date** : 23 octobre 2026
> **Statut du moteur** : Gelé (`PHASE_4_FROZEN`) — **Étude et propositions d'architecture uniquement**
> **Commande de reproduction** : `python -m local_app.study_outdated_amounts`
> **Issue associée** : [Issue #9 (Task 9)](https://github.com/SalimMabed/regassist-dz/issues/9)

---

## 1. Contexte et Problématique

### 1.1 Le risque juridique des montants financiers obsolètes
Dans le droit bancaire et financier algérien, les valeurs chiffrées (montants de capital social minimum, plafonds d'indemnisation des déposants, ratios de solvabilité, taux de réserves obligatoires, seuils de change) font l'objet de révisions périodiques par voie de règlements et d'instructions modificatifs de la Banque d'Algérie.

Lors des évaluations de la Phase 4, plusieurs cas critiques ont mis en lumière une vulnérabilité majeure des moteurs RAG standard :
- **Cas H129 (`docs/CAS_CRITIQUES_A_EXAMINER.md`)** : Interrogé sur le taux actuel des réserves obligatoires, le système a cité l'Instruction n° 02-2023 fixant le taux à **3 %** (valeur périmée), au lieu de l'Instruction n° 01-2026 en vigueur fixant le taux à **1 %**.
- **Cas Capital bancaire** : Le capital minimum des banques a évolué de **2,5 milliards DA** (Règlement n° 04-01) à **10 milliards DA** (Règlement n° 08-04) puis à **20 milliards DA** (Règlement n° 18-03).
- **Cas Garantie des dépôts** : Le plafond de garantie par déposant est passé de **600 000 DA** (Règlement n° 97-04) à **2 000 000 DA** (Règlement n° 20-04).

Si un modèle LLM synthétise une réponse à partir d'un ensemble de passages où coexistent des textes anciens et des textes modificatifs récents, le risque qu'il sélectionne un montant abrogé ou obsolète est critique.

### 1.2 Objectifs de l'Étude (Task 9)
Conformément aux spécifications de `docs/TASKS.md` et à la demande de Salim Mabed, cette étude :
1. **Quantifie** à l'échelle du corpus le volume d'articles modifiés/abrogés contenant des valeurs numériques.
2. **Mesure empiriquement** sur la recherche réelle (`agent.search` : BM25 + `e5-small` + reranker ONNX `mmarco`) la fréquence à laquelle des montants périmés co-occurrent avec ou devancent les montants applicables.
3. **Formule 3 propositions architecturales concrètes** pour le prochain dégel du moteur, tout en maintenant le moteur actuel strictement intact.

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

> **Constat majeur** : Plus de **40 %** des mentions de montants financiers dans le corpus proviennent de textes juridiquement dépassés (abrogés ou modifiés). La probabilité d'extraire un montant périmé par simple recherche de mots-clés est donc structurellement très élevée.

---

## 3. Évaluation Empirique sur la Recherche Réelle (`agent.search`)

Huit requêtes représentatives portant sur des valeurs financières modifiées au fil des ans ont été soumises au pipeline hybride de recherche gelé (BM25 + vectoriel dense + reranker de cross-attention) avec une fenêtre de récupération $K=6$.

### 3.1 Synthèse Statistique

| Métrique de recherche ($N=8$ cas types) | Résultat mesuré | Taux constaté |
|---|---|---|
| **Co-occurrence Périmé + Actif (dans le Top-6)** | **7 / 8** | **87.5 %** |
| **Inversion Temporelle (Passage périmé classé devant le texte actif)** | **4 / 8** | **50.0 %** |
| **Passage Périmé classé N°1 absolu (Top-1)** | **1 / 8** | **12.5 %** |

### 3.2 Tableau Détaillé par Cas d'Usage

| Identifiant | Thème réglementaire | Montant Actuel | Montants Périmés dans le corpus | Rang Actif | Rangs Périmés | Inversion Temporelle |
|---|---|---|---|---|---|---|
| `CASE-01` | **Capital minimum des banques** | 20 Mrds DA (`REG-18-03`) | 2,5 Mrds (`REG-04-01`), 10 Mrds (`REG-08-04`) | Rang 6 | **Rangs 2, 3** | **OUI (Périmé devance l'actif)** |
| `CASE-02` | **Capital minimum des étal. financiers** | 6,5 Mrds DA (`REG-18-03`) | 500 M (`REG-04-01`), 3,5 Mrds (`REG-08-04`) | Rang 4 | **Rang 2** | **OUI (Périmé devance l'actif)** |
| `CASE-03` | **Plafond Fonds de Garantie des Dépôts** | 2 000 000 DA (`REG-20-04`) | 600 000 DA (`REG-97-04`) | Non retrouvé | **Rangs 5, 6** | **OUI (Seul le périmé remonte)** |
| `CASE-04` | **Taux des réserves obligatoires (H129)** | 1 % (`INS-01-26`) | 2 %, 3 %, 8 %, 10 %, 12 % | **Rang 1** | Rangs 5, 6, 7... | NON (Actif en tête, mais périmés présents) |
| `CASE-05` | **Droit de change voyage (Allocation)** | 750 € (`INS-07-26`) | 15 000 DA (`INS-08-97`) | **Rang 1** | Rang 3 | NON (Périmé en embuscade à Rang 3) |
| `CASE-06` | **Ratio de solvabilité global** | 9,5 % (`REG-14-01`) | 8 % (`REG-91-09`) | **Rang 1** | Rang 6 | NON |
| `CASE-07` | **Coefficient de liquidité minimum** | 100 % (`REG-11-04`) | 60 % (`REG-91-11`), text. modif | Rang 2 | **Rang 1** | **OUI (Périmé devance l'actif)** |
| `CASE-08` | **Plafond division des grands risques** | 25 % (`REG-14-02`) | 25 % base modifiée (`REG-91-08`) | **Rang 1** | Rangs 4, 5 | NON |

---

## 4. Taxonomie des Causes d'Échec de la Recherche

Pourquoi un moteur de recherche RAG de pointe (BM25 + `e5-small` + cross-encoder) place-t-il si souvent des textes abrogés au-dessus des textes en vigueur ?

### Cause 1 : Asymétrie textuelle (Biais lexical du texte fondateur)
Les règlements fondateurs (ex. Règlement n° 04-01 fixant le capital à 2,5 milliards) contiennent des intitulés très explicites :
> *« Règlement n° 04-01 relatif au capital minimum des banques et établissements financiers... »*

En revanche, le texte modificateur (Règlement n° 18-03 fixant le capital à 20 milliards) a une rédaction laconique typique des textes d'amendement :
> *« L'article 2 du règlement n° 08-04 du 21 juillet 2008 est modifié et rédigé comme suit : Article 2 : Le capital des banques est fixé à... »*

Le score BM25 et le reranker récompensent la correspondance exacte entre la question (*« capital minimum des banques »*) et le titre fondateur, pénalisant le texte modificateur qui ne répète pas tous les mots-clés du domaine.

### Cause 2 : Insensibilité temporelle des embeddings denses
Le modèle d'embedding (`multilingual-e5-small`) et le cross-encoder (`mmarco-mMiniLMv2`) encodent la proximité sémantique conceptuelle. Pour eux :
$$\text{sim}(« 2,5\text{ milliards de DA} », « 20\text{ milliards de DA} ») \approx 0.95$$
Ils ne possèdent aucune notion intrinsèque de succession chronologique ni d'autorité normative d'une date ultérieure.

### Cause 3 : L'effet de citation inverse (L'anomalie H129)
Dans l'instruction n° 02-2023, le texte de l'article 2 est découpé par le parser au niveau de l'article cité :
> *« ... est modifié et rédigé comme suit : "Article 3 : Le taux des réserves obligatoires est fixé à 3 %..." »*

Le chunk a été indexé sous l'étiquette `INS-02-23.ar::article-3`. Or, aucun texte ne modifie *l'article 3 de l'instruction 02-2023* (qui n'a formellement que 2 articles) ; c'est *l'article 3 de l'instruction 02-2004* qui a été remplacé par l'instruction 01-2026 ! Le statut juridique calculé était donc faussement `ACTIVE`, trompant le modèle de langage qui a recopié le statut et la valeur périmée.

---

## 5. Trois Propositions d'Architecture pour le Prochain Dégel

Ces propositions sont conçues pour être intégrées lors du prochain cycle de révision du moteur, sans toucher au périmètre gelé actuel :

### Proposition A : Injection de Paires par Graphe de Remplacement (Retrieval Level)
* **Principe** : Tirer parti des relations `abroge_par`, `modifie_par`, `remplace_par` déjà présentes dans `legal_status.json`.
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
  1. Actuellement, `relations.json` lie principalement des textes (`REG-04-01` $\rightarrow$ `REG-08-04`).
  2. Structurer explicitement la chaîne de filiation :
     $$\text{REG-04-01 art. 2} \xrightarrow{\text{remplacé par}} \text{REG-08-04 art. 2} \xrightarrow{\text{remplacé par}} \text{REG-18-03 art. 2}$$
  3. Lors de l'indexation, le texte modificateur laconique hérite automatiquement des mots-clés conceptuels de l'article d'origine (expansion d'indexation ciblée), éliminant l'asymétrie lexicale BM25 sans modifier le texte juridique lui-même.

---

## 6. Conclusion et Feuille de Route

L'étude empirique de la Task 9 démontre qu'en matière de montants financiers, le problème principal n'est pas l'hallucination pure du LLM, mais **l'inversion temporelle à l'étape de recherche** (dans 50 % des cas, le texte périmé surclasse le texte en vigueur).

Les trois propositions formulées ci-dessus offrent une solution modulaire et robuste qui pourra être implémentée dès que le calendrier du projet autorisera le prochain dégel de l'infrastructure de recherche.
