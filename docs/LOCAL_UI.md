# Interface — assistant juridique, projet éducatif non officiel (phase 6)

Page web servie par l'application locale : `http://127.0.0.1:8790` (voir [LOCAL_DEPLOYMENT.md](LOCAL_DEPLOYMENT.md) pour le démarrage). Elle ne fait qu'**afficher** ce que renvoie le système gelé `PHASE_4_FROZEN` : elle n'ajoute aucune règle juridique, aucun score, aucune interprétation.

Technique : HTML + CSS + JavaScript sans dépendance, sans CDN, sans police ni image distante (`local_app/static/`). Tout texte venant des textes officiels ou de l'IA est inséré par `textContent`, jamais interprété comme du HTML.

## 1. Ce que dit clairement l'interface

* **En-tête** : pastille « PROJET ÉDUCATIF · NON OFFICIEL ».
* **Bandeau permanent** : projet éducatif non officiel ; ni affilié à la Banque d'Algérie ni approuvé par elle ; construit exclusivement à partir de textes publics publiés sur son site ; réponses rédigées par une intelligence artificielle, pouvant être incomplètes ou erronées, **non validées par un juriste**, ne constituant pas un avis juridique ; seul le texte officiel (PDF) fait foi.
* **Pied de page** : rappel en une ligne (projet éducatif non officiel · données publiques de la Banque d'Algérie · réponses rédigées par une IA à vérifier · pas un avis juridique).
* **Bouton « À propos »** : projet, données (publiques uniquement), fonctionnement, limites, vie privée (l'application ne conserve pas le texte des questions ; l'historique reste dans le navigateur et s'efface à volonté).

**Formulation volontaire : « construit à partir de données publiques », et non « entraîné sur »**. Aucun modèle n'a été entraîné ni affiné sur ces textes (règle du projet) : le système retrouve les passages pertinents au moment de la question et l'IA les lit pour rédiger. Le panneau « À propos » le dit explicitement (« n'a pas été entraînée ni spécialisée sur ces textes »).

## 2. Ce qui n'est PLUS affiché (détails techniques retirés)

Nom du modèle, moteur de recherche (« hybride », « reranker », « retrieval »), durées de traitement, état des composants, pastille « LOCAL », panneau « État du système », phase/statut internes (`PHASE_4_FROZEN`, `NO-GO PROVISOIRE`), identifiants de passage, volet « Traçabilité », règles et niveaux de confiance internes (`[règle A-1, confiance MEDIUM]`), `OCR_UNCERTAIN`, noms de scripts, ports. Les notes du système sont traduites en langage courant (ex. « écartée du contexte du LLM » devient « écartée de l'analyse » ; « OCR_UNCERTAIN » devient « À vérifier »), et les codes de statut que l'IA recopie parfois dans sa réponse (`ACTIVE`, `REPLACED`…) sont affichés avec leur libellé (« dernière version connue », « remplacé (version antérieure) »). Les routes techniques (`/api/status`, champs `model`, `retriever`, `durations_ms` de `/api/chat`) existent toujours pour l'administration et les tests, mais l'interface ne les montre pas. Un test automatique vérifie l'absence de ce vocabulaire dans le texte affiché.

Ce qui est conservé parce que c'est utile pour lire et vérifier : sources et extraits, référence, type, date, article, page, statut juridique en clair, relations (« Modifié par… », « Abroge… »), alertes, avertissements, liens « PDF officiel » et « Page du site », historique, nouvelle conversation.

## 3. Disposition

| Zone | Contenu |
|---|---|
| Colonne de gauche | « Nouvelle conversation », historique des questions, « Effacer l'historique » |
| Zone centrale | rappel de la question, puis **Sources** (à gauche) et **Réponse** (à droite) |
| Bas de page | saisie (Entrée envoie, Maj+Entrée = retour à la ligne), compteur `n / 500`, « Envoyer » ; message simple si le service est indisponible |

Sur écran étroit (< 800 px), les volets s'empilent, sans défilement horizontal.

## 4. Parcours d'une question

1. L'utilisateur saisit 3 à 500 caractères.
2. Le navigateur envoie la question à l'application (même origine), qui l'applique **telle quelle** au système gelé (recherche dans les textes, rédaction par l'IA).
3. Pendant le traitement : « Recherche dans les textes puis rédaction de la réponse. Cela peut prendre jusqu'à une minute… » avec un compteur de secondes. Il n'y a pas de flux : sources et réponse apparaissent ensemble.
4. Le résultat est affiché et ajouté à l'historique de ce navigateur. Chaque question est traitée **indépendamment** des précédentes.

## 5. Affichage des sources

Chaque source est une carte. Un champ n'est affiché **que s'il existe**.

| Affiché | Remarque |
|---|---|
| `S1`… et « Cité dans la réponse » | seulement pour une réponse rédigée |
| Référence et intitulé officiel | |
| Type de texte, date en toutes lettres, article, page(s) du PDF, rubrique | |
| **Statut juridique** | `ACTIVE` = « Dernière version connue », `MODIFIED` = « Modifié ultérieurement », `REPLACED` = « Remplacé (version antérieure) », `ABROGATED` = « Abrogé d'après les textes », `HISTORICAL` = « Valeur d'une période échue », `UNKNOWN` = « Vigueur non déterminée ». **Jamais « en vigueur »** : le site officiel ne publie pas de statut de vigueur. |
| Statut du texte | « STATUT À VÉRIFIER » |
| Avertissements | document à vérifier ; texte numérisé (reconnaissance automatique) ; « Valeur numérique à vérifier dans le PDF » ; alerte « texte modifié/abrogé » ; relations |
| Extrait | reproduit tel quel (replié au-delà de 9 lignes) |
| Liens | « PDF officiel », « Page du site » (nouvel onglet ; seule fonction qui demande Internet) |

Jamais affichés : scores et similarités internes. Un score interne n'est pas une information juridique.

## 6. Affichage de la réponse

| Situation | Affichage |
|---|---|
| **Réponse rédigée** | mention « rédigée par une intelligence artificielle uniquement à partir des sources ci-contre… vérifiez chaque citation dans le texte officiel (PDF) » ; pastille « n avertissement(s) » ; texte avec citations `[S1]` cliquables ; encadré jaune « À vérifier avant tout usage » avec toutes les notes ; avertissement juridique |
| **Pas de réponse directe mais des textes retrouvés** (rédaction impossible, ou refus de l'IA) | « **Je ne peux pas répondre directement, mais voici quelques textes qui pourraient vous aider à trouver la réponse :** », puis chaque texte décrit (référence en gras suivie de l'intitulé officiel, type, date, passages cliquables, statut, relations, liens), puis « Pourquoi pas de réponse directe » avec une cause, en langage courant |
| Aucun texte retrouvé (refus de la recherche) | encadré « Aucune réponse établie » + phrase de refus du système + rappel que cela ne prouve pas l'absence de disposition |
| Question ambiguë | encadré « Précision nécessaire » |
| Erreur | « La question n'a pas pu être traitée » + message simple, jamais de détail technique |

La description des textes vient **uniquement des métadonnées** (aucun LLM) : le modèle vient de ne pas pouvoir répondre, et une description générée pourrait inventer. Ces textes sont les plus proches de la question d'après la recherche ; ils ne constituent pas une réponse et ne contiennent pas nécessairement l'information recherchée (l'interface le dit). Messages de cause : « Le service de rédaction des réponses est momentanément indisponible. » (service éteint) ou « La réponse n'a pas pu être rédigée correctement (question trop large ou réponse trop longue)… essayez une question plus précise » (sortie coupée ou illisible).

Principe : des sources insuffisantes, ambiguës ou non établies ne doivent jamais ressembler à une réponse certaine.

## 7. Historique local

Stocké dans le **localStorage de ce navigateur** (clé `regassist.history.v1`) : aucune base de données, rien n'est envoyé ailleurs. Limites : 30 conversations / 150 questions. Cliquer une question restitue la réponse enregistrée (« non recalculée »). « Nouvelle conversation » vide la zone de travail ; « Effacer l'historique » demande une confirmation (second clic dans les 4 s). Si le navigateur refuse le stockage, l'historique reste en mémoire et l'interface le signale. L'historique contient des extraits des textes : ne pas l'exporter vers un service tiers.

## 8. Accessibilité

Libellés associés aux champs, zones `aria-live` pour les réponses, focus visible, clavier (Entrée, Maj+Entrée, Échap pour fermer « À propos »), contraste élevé, aucune animation, aucun emoji, polices système, fonctionne sans Internet.

## 9. Limites connues

* Pas de flux ni d'annulation : le pipeline gelé renvoie sa réponse d'un bloc (jusqu'à une minute) ; une seule question à la fois (une seconde reçoit « Une question est déjà en cours de traitement »).
* Pas de mémoire de conversation ; limite de 500 caractères par question (non retouchée : refusée si trop longue).
* Les cas connus du système gelé (retrouvailles incomplètes sur les questions très larges, refus à tort possible, statut de vigueur parfois inexact, OCR arabe, conflits de dates FR/AR) **ne sont pas corrigés** par l'interface : voir `docs/PHASE_4_FROZEN.md` et `docs/NOTE_AU_JURISTE.md`.
* Testée dans Edge/Chrome (Chromium) ; interface en français.
