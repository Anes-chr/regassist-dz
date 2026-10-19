# Gouvernance, Confidentialité et Propriété Intellectuelle

Ce document formalise les principes de gouvernance, de confidentialité et de gestion des licences pour le projet **RegAssist DZ** dans le cadre de la compétition Thirduni (Cohorte 1).

---

## 1. Nature et statut du projet

* **Projet éducatif et de recherche indépendant** : RegAssist DZ n'est ni affilié à la Banque d'Algérie, ni approuvé, ni mandaté par elle.
* **Statut d'évaluation (NO-GO PROVISOIRE)** : le système est figé (`PHASE_4_FROZEN`) pour permettre une validation juridique humaine indépendante (Tâche T1). Les réponses générées ne constituent en aucun cas un avis juridique ; seul le texte officiel publié au Journal Officiel ou sur le site officiel de la Banque d'Algérie fait foi.

---

## 2. Équipe et rôles de co-auteurs

Le projet est co-développé par :

1. **Salim Mabed** :
   * Architecture du moteur gelé de recherche (`agent_fr/`, `boa_pipeline/`, `llm_local/`).
   * Pipeline d'ingestion et d'OCR bilingue (arabe / français) des 1 085 documents officiels.
   * Modélisation du graphe de relations temporelles et juridiques (modifications, abrogations, consolidations).
   * Conception du protocole de gel `PHASE_4_FROZEN` et exécution des évaluations comparatives.

2. **Chouari Mohammed Anes** :
   * Conception et implémentation de la couche de déploiement Linux de production (`deploy/` : Gunicorn WSGI multi-thread, configuration Nginx durcie, services systemd).
   * Sécurisation applicative de production : filtrage strict Host / Origin, limitation de débit native par IP (`RateLimiter`) avec en-têtes HTTP 429 et `Retry-After`.
   * Refonte de l'espace de travail utilisateur et de l'interface de vérification des sources (`local_app/`).
   * Résolution cryptographique multiplateforme des clés de vecteurs d'exécution (`deploy/ensure_vectors.py`).
   * Automatisation des tests et pipeline d'intégration continue GitHub Actions (`.github/workflows/ci.yml`).

---

## 3. Sécurité et protection des données (Privacy Policy)

RegAssist DZ applique le principe de protection des données dès la conception (*Privacy by Design*) :

* **Zéro journalisation des requêtes utilisateur** : par défaut, le texte des questions posées par les utilisateurs n'est jamais écrit sur le disque. Les fichiers de journalisation (`access.log` et `api.log`) n'enregistrent que la méthode HTTP, le chemin, le code de statut, les durées de traitement et la longueur brute de la question (nombre de caractères). L'enregistrement du texte des requêtes nécessite l'activation explicite d'une variable d'environnement dédiée (`LOCAL_APP_LOG_QUESTIONS=1`).
* **Zéro télémétrie tierce** : aucun traceur analytique, CDN, balise externe, police distante ou script tiers n'est utilisé. L'application applique une politique de sécurité de contenu stricte (`Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'`).
* **Inférence locale sans fuite de données** : tous les calculs (vectorisation lexicale BM25, embeddings multilingues ONNX, reclassement cross-encoder et génération de réponse par le modèle Qwen3-4B) sont exécutés localement sur le processeur (CPU) de la machine hôte. Aucune donnée ne quitte le serveur.
* **Historique côté client** : l'historique des conversations est stocké exclusivement dans le stockage local du navigateur de l'utilisateur (`localStorage`) et peut être purgé à tout moment en un clic.

---

## 4. Propriété intellectuelle et licences (Split Licensing)

Le projet applique une séparation stricte entre les différentes composantes :

### 4.1. Code logiciel développé
Le code source de l'application, les tests, les scripts d'administration et les fichiers de configuration développés par l'équipe font l'objet d'un accord de licence en cours de finalisation entre les co-auteurs. Aucun fichier de licence unilatéral ne peut être appliqué sans le consentement mutuel de Salim Mabed et Chouari Mohammed Anes.

### 4.2. Corpus réglementaire de la Banque d'Algérie
Les textes réglementaires (règlements, instructions, notes et circulaires) reproduits dans le dossier `corpus/` sont des documents publics émanant de la **Banque d'Algérie** ([bank-of-algeria.dz](https://www.bank-of-algeria.dz)).
* Ils demeurent la propriété exclusive de leurs auteurs institutionnels.
* Ils sont inclus dans ce dépôt uniquement à des fins de reproductibilité technique, de recherche académique et d'accès éducatif.

### 4.3. Modèles de langage et composants tiers
* **Qwen3-4B-Instruct-2507** : licence Apache-2.0 (Alibaba Cloud / Qwen team).
* **multilingual-e5-small** : licence MIT (Microsoft Corporation).
* **mmarco-mMiniLMv2-L12-H384** : licence Apache-2.0 (Cross-Encoder / Hugging Face).
* **llama.cpp** : licence MIT (Georgi Gerganov et contributeurs).
