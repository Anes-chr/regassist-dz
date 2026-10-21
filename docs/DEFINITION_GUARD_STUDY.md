# Étude Empirique du Garde-Fou de Définition (Task 8 / T8)

> **Projet** : RegAssist DZ — Couche d'accès applicative (`local_app/grounding.py`)  
> **Date de mesure** : 21 octobre 2026  
> **Statut du moteur** : Gelé (`PHASE_4_FROZEN`)  
> **Commande de reproduction** : `python local_app/measure_definition_guard.py`  
> **Suites de tests automatisées** : `python local_app/tests/test_grounding.py` (8/8 passés)

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

### 1.2 Objectif de la Task 8
Mesurer quantitativement et qualitativement l'impact du garde-fou implémenté dans `local_app/grounding.py` :
- Vérifier qu'il n'entraîne **aucune régression** sur les bancs de tests gelés (taux de déclenchement sur les 130 questions du Benchmark Humain Phase 4).
- Évaluer le taux de **vrais positifs** (définitions infondées ou hallucinées correctement interceptées et transformées en refus poli).
- Évaluer le taux de **faux positifs** (définitions légitimes du corpus bancaire qui seraient retirées à tort).
- Valider la robustesse aux variations syntaxiques (casse, ponctuation, pluriels, formulations).

---

## 2. Mécanisme du Garde-Fou (`local_app/grounding.py`)

Le garde-fou opère exclusivement dans la **couche d'accès applicative**, sans toucher aux modules gelés (`agent_fr/`, `llm_local/`) :

1. **Normalisation typographique (`normalise_question`)** :  
   Les apostrophes et espaces non standards (clavier mobile, Word : `’`, `‘`, `ʼ`, `\u00A0`) sont convertis en ASCII standard avant transmission au moteur de recherche.
2. **Identification du terme à définir (`definition_term`)** :  
   Reconnaît les motifs explicites de définition en français :
   - Amorces en tête : *« c'est quoi »*, *« qu'est-ce que »*, *« définition de »*, *« que signifie »*, *« que veut dire »*, *« explique-moi »*, *« peux-tu m'expliquer »*...
   - Amorces en fin : *« c'est quoi »*, *« ça veut dire quoi »*, *« ça signifie quoi »*.
   - Filtre strict : termes nominaux de 1 à 5 mots pleins, sans chiffres, sans verbes conjugués, sans pronoms.
3. **Vérification d'ancrage (`unsupported_term`)** :  
   Vérifie que la racine lexicale du terme figure dans au moins l'un des textes retrouvés par le moteur. Si le terme est absent, la réponse est transformée en un refus explicite (`terme_absent`) :
   > *« Le terme « {terme} » n'apparaît dans aucun des textes retrouvés : je ne peux pas le définir à partir du corpus, et je préfère ne pas proposer une définition construite à partir de textes qui parlent d'autre chose. »*

---

## 3. Résultats Quantitatifs de l'Étude

L'évaluation a été exécutée sur **546 questions** issues de l'ensemble des jeux de données du projet :

| Jeu de données | Total Questions | Reconnues comme Définition | Déclenchements Garde-Fou | Faux Positifs (erreurs) | Vrais Positifs (bloqués) |
|---|---|---|---|---|---|
| **Benchmark Humain Phase 4 (Dev + Test)** | 130 | 0 (0.0 %) | 0 | 0 | 0 |
| **Suites d'évaluation Gold (v2 à v5 & OOS)** | 199 | 1 (0.5 %) | 1 | 0 | 1 (D05 Hors-portée) |
| **Régression Phase 4 (Hybride + Reranker)** | 174 | 0 (0.0 %) | 0 | 0 | 0 |
| **Jeu ciblé : Définitions Réglementaires Soutenues** | 20 | 20 (100 %) | 0 | **0 (0.0 % FP)** | N/A (conservées) |
| **Jeu ciblé : Définitions Infondées / Hallucinées** | 15 | 15 (100 %) | 15 | 0 | **15 (100 % TP)** |
| **Jeu frontière : Questions non-définitions** | 8 | 0 (0.0 %) | 0 | 0 | N/A |
| **TOTAL** | **546** | **36** | **16** | **0 (0.0 % FP)** | **16 (100 % TP)** |

### Métriques Clés :
- **Taux de Faux Positifs (FP)** : **0.0 %** (Aucune définition valide soutenue par le corpus n'a été bloquée).
- **Précision** : **100.0 %** ($\frac{16}{16 + 0}$).
- **Rappel sur termes absents** : **100.0 %** ($\frac{16}{16 + 0}$).
- **Impact sur le Benchmark Officiel (130 questions)** : **0 modification**. Le benchmark existant est composé de questions factuelles, chiffrées et procédurales (ex. *« Quel est le capital minimum d'une banque ? »*, *« À quel taux s'applique la réserve obligatoire ? »*), aucune ne demandant de définition terminologique. Le garde-fou ne perturbe donc en rien les scores d'évaluation gelés.

---

## 4. Analyse Détaillée des Cas Remarquables

### Cas 1 : « C’est quoi l’allocation touristique ? » (Cas d'origine)
- **Détection** : Reconnue comme demande de définition du terme `allocation touristique`.
- **Textes retrouvés** : Règlement 91-06 (rapatriement d'une dépouille), Instruction 83-92.
- **Vérification d'ancrage** : Les mots `allocation` et `touristique` apparaissent séparément, mais le lemme combiné `allocation touristique` est absent de tous les textes.
- **Avant garde-fou** : Réponse générée fausse affirmant que l'allocation touristique sert à rapatrier une dépouille en cas de décès (50 000 DA).
- **Après garde-fou** : Refus immédiat avec le motif `terme_absent` et explication transparente. Cursus préservé, 0 hallucination transmise à l'utilisateur.

### Cas 2 : Question Hors-Portée D05 (« Explique le principe de la photosynthèse. »)
- **Détection** : Reconnue comme demande d'explication du terme `principe de la photosynthese`.
- **Textes retrouvés** : Chunks bancaires sans aucun rapport.
- **Comportement du garde-fou** : Bloque immédiatement toute velléité d'extrapoler une définition à partir du vocabulaire bancaire et garantit un refus propre.

### Cas 3 : Définitions Réglementaires Authentiques (Validation Zéro Faux Positif)
Toutes les définitions officielles de la Banque d'Algérie testées ont été validées sans entrave :
- *« C'est quoi le Salam ? »* → Conservée avec citations (Règlement 20-02).
- *« Qu'est-ce qu'un prestataire de services de paiement ? »* → Conservée avec citations (Loi 23-09).
- *« C'est quoi la monnaie électronique ? »* → Conservée avec citations (Règlement 20-03).
- *« Définition du droit de change pour voyage à l'étranger »* → Conservée avec citations (Instruction 07-2026).
- *« C'est quoi le ratio de solvabilité ? »* → Conservée avec citations (Instruction 03-2020).
- *« Explique-moi le fixing »* → Conservée avec citations (Règlement 07-01).

---

## 5. Conclusions et Recommandations (Lien avec T1 & T7)

1. **Efficacité confirmée** : Le garde-fou de définition remplit exactement son rôle préventif. Il élimine une classe d'hallucinations particulièrement insidieuse (l'amalgame de termes distincts composant une fausse définition) sans dégrader la restitution des concepts juridiques réels.
2. **Recommandation pour la Task 7 (Passerelle termes d'usage ↔ termes du corpus)** :  
   L'assistant refuse aujourd'hui légitimement « allocation touristique » parce que l'expression n'est pas dans le corpus. Une fois la validation juridique obtenue (Task 1), une passerelle d'équivalence explicite et auditée pourra être ajoutée dans `local_app/` :
   $$\text{« allocation touristique »} \longrightarrow \text{« droit de change pour voyage à l’étranger » (Instruction 07-2026)}$$
3. **Recommandation pour le prochain gel du moteur** :  
   Conserver ce garde-fou en première ligne dans la couche de service web.
