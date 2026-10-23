# Étude Empirique du Garde-Fou de Définition (Task 8 / T8)

> **Projet** : RegAssist DZ — Couche d'accès applicative (`local_app/grounding.py`)
> **Date de mesure** : 23 octobre 2026 (Mise à jour suite à la revue de Salim Mabed)
> **Statut du moteur** : Gelé (`PHASE_4_FROZEN`)
> **Commande de reproduction** : `python -m local_app.measure_definition_guard`
> **Suites de tests automatisées** : `python local_app/tests/test_grounding.py` (8/8 passés)
> **Issue associée** : [Issue #8 (Task 8)](https://github.com/SalimMabed/regassist-dz/issues/8)

---

## 1. Contexte et Problématique

### 1.1 Le cas d'origine (18 octobre 2026)
Lors des premiers essais en usage réel de l'application locale, la question suivante a été posée :
> *« C’est quoi l’allocation touristique ? »*

Le moteur de recherche hybride a retrouvé des textes réglementaires contenant les mots « allocation » et « touristique » séparés par d'autres termes (notamment le Règlement n° 91-06 et l'Instruction n° 83-92 relatifs au *rapatriement de dépouilles mortelles* de nationaux en voyage touristique ou d'affaires). Le modèle LLM local a synthétisé une définition erronée :
> *« L'allocation touristique est une allocation en devises attribuée aux nationaux résidents en voyage touristique ou d'affaires à l'étranger, en cas de décès du malade ou du national résidant… montant fixé à 50.000 Dinars [S3]. »*

Or :
1. L'expression exacte « allocation touristique » ne figure dans **aucun des 7 789 passages** du corpus réglementaire de la Banque d'Algérie (recherche exhaustive).
2. Dans le droit bancaire algérien, le dispositif visé par l'usage courant est en réalité le **« droit de change pour voyage à l’étranger »** (Instruction n° 08-97 abrogée par l'Instruction n° 05-2025, puis par l'Instruction n° 07-2026 du 13 juillet 2026 fixant le plafond à 750 €).
3. La décision de répondre ou refuser oscillait selon la casse ou le type d'apostrophe typographique (`’` vs `'`).

### 1.2 Objectif de la Task 8 et Précision Méthodologique (Revue de Salim Mabed)
Comme l'a souligné Salim Mabed lors de sa revue :
> *« Les 43 questions construites utilisent des textes retrouvés écrits à la main, de sorte que les 0 % de faux positifs et 100 % de précision testent la logique d'appariement, pas la recherche réelle, et seulement 1 des 503 questions existantes est une définition. Pour une vraie mesure, passez les 43 questions plus environ 50 de plus dans `agent.search` (sans LLM) pour obtenir les vrais passages retrouvés, appliquez `unsupported_term` sur ceux-ci, et rapportez combien de définitions correctes sont retirées. »*

Cette étude distingue donc rigoureusement :
- **Partie 1** : Le test logique sur contextes construits (43 cas).
- **Partie 2** : L'évaluation empirique sur recherche réelle (`agent.search`, 100 questions).
- **Partie 3** : La vérification de non-régression sur les 503 questions historiques du dépôt.

---

## 2. Mécanisme du Garde-Fou (`local_app/grounding.py`)

Le garde-fou opère exclusivement dans la **couche d'accès applicative**, sans modifier les modules gelés (`agent_fr/`, `llm_local/`) :

1. **Normalisation typographique (`normalise_question`)** :
   Les apostrophes et espaces non standards (clavier mobile, Word : `’`, `‘`, `ʼ`, `\u00A0`) sont convertis en ASCII standard avant transmission au moteur de recherche.
2. **Identification du terme à définir (`definition_term`)** :
   Reconnaît les motifs explicites de définition en français :
   - Amorces en tête : *« c'est quoi »*, *« qu'est-ce que »*, *« définition de »*, *« que signifie »*, *« que veut dire »*, *« explique-moi »*, *« peux-tu m'expliquer »*...
   - Amorces en fin : *« c'est quoi »*, *« ça veut dire quoi »*, *« ça signifie quoi »*.
   - Filtre strict : syntagmes nominaux de 1 à 5 mots pleins, sans chiffres, sans verbes conjugués, sans pronoms.
3. **Vérification d'ancrage (`unsupported_term`)** :
   Vérifie que la racine lexicale du terme figure dans au moins l'un des textes retrouvés par le moteur. Si le terme est absent, la réponse est transformée en un refus explicite (`terme_absent`) :
   > *« Le terme « {terme} » n'apparaît dans aucun des textes retrouvés : je ne peux pas le définir à partir du corpus, et je préfère ne pas proposer une définition construite à partir de textes qui parlent d'autre chose. »*

---

## 3. Partie 1 : Test Logique sur Contextes Construits (43 Cas)

Cette première étape évalue la logique pure de normalisation et d'appariement lexical en isolation contre des extraits textuels synthétiques contrôlés (sans faire appel au moteur de recherche).

| Catégorie de test | Nombre de cas | Résultat attendu | Vrais Positifs (TP) | Faux Positifs (FP) | Vrais Négatifs (TN) | Faux Négatifs (FN) |
|---|---|---|---|---|---|---|
| **Définitions soutenues (terme présent dans l'extrait)** | 20 | Préservée | 0 | **0** | **20** | 0 |
| **Définitions non soutenues (terme absent ou séparé)** | 15 | Retirée | **15** | 0 | 0 | **0** |
| **Questions frontières (non-définitions)** | 8 | Bypassed | 0 | 0 | 8 | 0 |
| **TOTAL CONSTRUIT** | **43** | — | **15** | **0 (0.0 % FP)** | **28** | **0 (0.0 % FN)** |

* **Précision logique** : **100.0 %** ($\frac{15}{15 + 0}$).
* **Rappel logique** : **100.0 %** ($\frac{15}{15 + 0}$).
* **Portée du test** : Valide que l'algorithme ne génère pas de faux positifs lorsque le terme est effectivement présent dans le texte fourni.

---

## 4. Partie 2 : Évaluation Empirique sur Recherche Réelle (`agent.search`, 100 Questions)

Pour mesurer l'impact réel en conditions opérationnelles, **100 questions** ont été soumises au moteur de recherche hybride gelé (`agent.search` : BM25 + `e5-small` + reranker ONNX `mmarco-mMiniLMv2`, sans génération LLM, durée totale : 129,5 s). Le filtre `unsupported_term` a ensuite été appliqué sur les véritables passages retrouvés ($K=5$).

### 4.1 Synthèse Globale

| Groupe de questions | Total Questions | Comportement Attendu | Mesure Observée | Taux |
|---|---|---|---|---|
| **Groupe A : Termes réglementaires existants dans le corpus** | 48 | Préservé (terme dans les sources) | **41 préservées**<br>**7 retirées (Faux Positifs)** | **85.4 % Préservation**<br>**14.6 % Faux Positifs** |
| **Groupe B : Termes informels / hors-corpus / crypto** | 38 | Retiré (terme absent des sources) | **36 retirées (Vrais Positifs)**<br>**2 manquées (Faux Négatifs)** | **94.7 % Interception**<br>**5.3 % Échappement** |
| **Groupe C : Questions frontières non-définitions** | 14 | Ignoré par le filtre | **14 ignorées (Bypassed)** | **100.0 % Préservation** |

---

### 4.2 Analyse Détaillée des 7 Faux Positifs (Définitions Réglementaires Retirées à Tort)

Lors de la recherche réelle dans le corpus de 7 789 passages, 7 définitions légitimes ont été interceptées à tort par le garde-fou (taux de FP de **14.6 %**). L'inspection détaillée montre les causes exactes de ces retraits :

| ID | Question posée | Terme extrait | Passages retrouvés par `agent.search` | Cause exacte du retrait (Faux Positif) |
|---|---|---|---|---|
| `REAL-S09` | *« C'est quoi la Moudharaba ? »* | `moudharaba` | Règlement 20-02, Instruction 03-20 | **Divergence de translittération** : Le texte réglementaire officiel utilise la graphie arabe translittérée *« Mudaraba »* ou *« Moudaraba »*. |
| `REAL-S14` | *« C'est quoi un établissement de paiement ? »* | `établissement de paiement` | Règlement 92-02, Règlement 05-07 | **Profondeur de recherche ($K=5$)** : Le moteur remonte des passages généraux sur les prestataires de services de paiement et les banques ; l'article spécifique de la Loi 23-09 définissant l'établissement de paiement n'était pas dans le Top-5. |
| `REAL-S20` | *« C'est quoi les fonds propres prudentiels ? »* | `fonds propres prudentiels` | Règlement 14-01 (ratios prudentiels) | **Vocabulaire composite** : Le corpus détaille les *« fonds propres de base »* et *« fonds propres complémentaires »*, mais n'utilise pas le syntagme figé exact *« fonds propres prudentiels »*. |
| `REAL-S21` | *« Qu'est-ce que le capital minimum d'une banque ? »* | `capital minimum d'une banque` | Règlement 08-02, Règlement 04-01 | **Désaccord flexionnel** : Le texte officiel stipule *« Le capital minimum des banques »* (pluriel *des banques* vs singulier *d'une banque*). La correspondance de sous-chaîne multi-mots stricte n'a pas toléré la variation d'article. |
| `REAL-S42` | *« C'est quoi un aval bancaire ? »* | `aval bancaire` | Instruction 07-95, Instruction 08-02 | **Qualificatif surajouté** : Le texte réglementaire emploie le terme simple *« l'aval »* ou *« donner son aval »*, jamais *« aval bancaire »*. |
| `REAL-S43` | *« Qu'est-ce que le cautionnement bancaire ? »* | `cautionnement bancaire` | Loi 23-09, Règlement 25-03 | **Qualificatif surajouté** : Le corpus réglementaire utilise *« cautionnement »* sans l'adjectif *« bancaire »*. |
| `REAL-S48` | *« C'est quoi le droit au compte bancaire ? »* | `droit au compte bancaire` | Instruction 03-2012 | **Nom officiel du dispositif** : L'Instruction 03-2012 régit expressément *« le droit au compte »*. |

> **Conclusion sur les Faux Positifs** :
> Le filtre actuel à $K=5$ conserve **85.4 %** des définitions officielles courantes (*Salam*, *Mourabaha*, *Ijara*, *Sukuk*, *monnaie électronique*, *PSP*, *ratio de solvabilité*, *fonds propres de base*, *réserves obligatoires*, *fixing*, *crédit documentaire*, *crédit-bail*, *affacturage*...).
> Les 14.6 % de retraits proviennent principalement de **variantes de formulation de l'utilisateur** (adjectifs surajoutés comme « bancaire », pluriels, translittérations alternatives) ou de passages pertinents relégués au-delà du rang 5.

---

### 4.3 Analyse des 2 Faux Négatifs (Termes Hors-Corpus Non Bloqués)

Sur les 38 questions portant sur des termes inexistants dans le corpus, **36 (94.7 %)** ont été correctement interceptées (*allocation touristique*, *square Port-Saïd*, *dinar parallèle*, *marché noir des devises*, *hawala*, *tontine informelle*, *bitcoin*, *stablecoin*, *carte Paysera*, *compte secret*, *hedge fund*...).

Seules 2 questions n'ont pas été bloquées par le filtre :
1. `REAL-U12` : *« Qu'est-ce que l'usure entre particuliers ? »*
   *Cause* : Présence de la préposition *« entre »*, exclue de la regex nominale de `definition_term(q)` qui a renvoyé `None`. La question a donc été traitée comme une question générale sans passer par le filtre d'ancrage.
2. `REAL-U20` : *« C'est quoi le livret A ? »*
   *Cause* : La lettre unique majuscule *« A »* est ignorée par le découpage standard des noms communs.

---

## 5. Partie 3 : Impact sur les 503 Questions Existantes du Dépôt

Pour garantir l'absence totale d'effet de bord sur l'existant, les 503 questions historiques des bancs d'évaluation du projet ont été rejouées :

| Banc de test existant | Nombre de questions | Détectées comme Définition | Retirées par le Garde-Fou | Taux de Régression |
|---|---|---|---|---|
| **Benchmark Humain Phase 4 (`dev` + `test`)** | 130 | 0 | 0 | **0.0 % (Aucune régression)** |
| **Banc de Régression Phase 4 (`hybrid_rerank`)** | 174 | 0 | 0 | **0.0 % (Aucune régression)** |
| **Suites Gold & Out-of-Scope (`v2` à `v5`)** | 199 | 1 | 1 | **100 % Justifié** |
| **TOTAL EXISTANT** | **503** | **1** | **1** | **0.0 % de régression** |

* Le **Benchmark Humain Phase 4 (130 questions)** ne comporte aucune demande de définition terminologique générale : il teste des règles précises (*« Quel est le capital minimum ? »*, *« À quel taux s'applique la réserve obligatoire ? »*). Le garde-fou reste donc totalement transparent vis-à-vis des scores gelés.
* L'unique question interceptée dans les suites Gold est la question `D05` : *« Explique le principe de la photosynthèse »* (question hors-portée). Le garde-fou a immédiatement bloqué la tentative de générer une réponse à partir de textes bancaires, prouvant son efficacité protectrice.

---

## 6. Conclusions et Recommandations (Lien avec T1 et T7)

1. **Mesure réelle établie** :
   - Sur contextes synthétiques (Partie 1), le garde-fou atteint 100 % de précision logique.
   - Sur la recherche réelle (`agent.search`, Partie 2), il préserve **85.4 %** des définitions réglementaires légitimes et bloque **94.7 %** des termes informels ou hallucinés.
2. **Gestion des Faux Positifs (14.6 %)** :
   Les retraits observés sont des retraits préventifs de sécurité : le système préfère avouer son ignorance plutôt que de broder une fausse définition (comme sur le cas du rapatriement de corps pour l'allocation touristique).
3. **Piste pour la Task 7 (Passerelle termes d'usage ↔ termes du corpus)** :
   Pour les notions usuelles non reconnues ou les variantes d'appellation (*« allocation touristique »* $\rightarrow$ *« droit de change pour voyage à l'étranger »*, ou *« établissement de paiement »*), une passerelle de synonymie juridique validée par un juriste (Task 1) permettra de résoudre le problème en amont de la recherche.
