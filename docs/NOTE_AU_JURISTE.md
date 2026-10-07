# RegAssist DZ — note au juriste (une page)

**Statut : NO-GO PROVISOIRE** — validation humaine absente, TEST v2 absent.

Le système est techniquement fonctionnel et entièrement local. La recherche hybride avec reranking est actuellement la meilleure architecture testée. Plusieurs problèmes objectifs du corpus et de l'OCR ont été corrigés.
**Cependant, aucune conclusion sur la fiabilité juridique ne doit être tirée des scores automatiques actuels** : les jeux ont été élaborés avec assistance IA et n'ont pas encore été validés par un juriste.
La question n'est pas « le système est-il bien fait ? » mais : **cette réponse est-elle juridiquement correcte et correctement sourcée ?**

**Limites connues.** Questions, réponses attendues, articles et statuts attendus ont été rédigés par l'IA qui a construit le système (biais possible) ; la notation automatique est stricte, parfois injuste, parfois trop indulgente (H129).
Le corpus est ce que le site expose (1 085 documents ; « actuel » = version la plus récente du corpus ; 337 textes de statut indéterminé ; 20 documents sans date). Le modèle de génération est petit (4 milliards de paramètres) : il peut refuser à tort, mélanger deux textes ou recopier une date de référence fournie par le système.
TEST v1 est consommé ; une mesure indépendante exige un TEST v2 que vous rédigeriez.

**OCR arabe.** Défaut établi : le symbole « % » placé devant une valeur est lu comme des chiffres (« 902.75 » pour « 2,75 % »). Un second moteur d'OCR testé n'y change rien. Le système compare ces valeurs au texte français quand il existe et affiche `OCR_UNCERTAIN` (80 passages) ; il ne corrige rien en silence. Le PDF officiel fait foi.

**H120** (compte en devises, question en arabe) — *avant la correction de l'analyse des articles arabes* : refus à tort ; *après* : réponse hors sujet (autre instruction citée, « solde en crédit » au lieu de « soldes débiteurs »).
À dire : question valide (« les personnes mentionnées » sans antécédent) ? source retrouvée pertinente ? réponse incorrecte ? le système aurait-il dû refuser ?

**H129** (taux « actuel » des réserves obligatoires) — une **valeur périmée** (3 %) **présentée comme actuelle** (« ACTIVE ») ; la notation automatique **ne la compte pas comme erreur critique** (et juge le statut correct). La valeur actuelle est 1 % (INS-01-26).
À dire : erreur juridique critique, ou autre catégorie ? Cet écart notation automatique / analyse qualitative est à documenter, pas à corriger. Ni H120 ni H129 n'ont été corrigés (fiche : `docs/CAS_CRITIQUES_A_EXAMINER.md`).

**Trois conflits de dates FR / AR** (fiche : `docs/ARBITRAGE_JUMEAUX_FR_AR.md`) — REG-90-01 (4 juin / 4 juillet 1990), REG-02-01 (20 / 17 février 2002), REG-06-01 (14 mai / 7 septembre 2006). **Personne n'a choisi** : à vous d'arbitrer (FR, AR, deux textes distincts, indéterminé).

**Protocole.** (1) `review/benchmark_review_p4.html` : 130 questions, 5 oui / non / ne sait pas + classement (CORRECT, INCORRECT, AMBIGU, QUESTION MAL FORMULÉE, SOURCE INCORRECTE, RÉPONSE ATTENDUE INCORRECTE) ; exporter.
(2) `review/human_eval_p4.html` : 60 réponses ; source, article, version, réponse, citation, justification, hallucination (non / juridique / factuelle / métadonnée interne) ; exporter. (3) Fiches des cas critiques et des conflits.
Vos réponses sont enregistrées telles quelles, sans effet automatique sur le système ; le recalcul compare l'hallucination humaine au seuil fixé avant le test (10 %), **non modifié**.
(4) Ensuite seulement, TEST v2 : questions rédigées indépendamment → validation → gel → empreintes → **une seule exécution** → résultats, sans aucune modification du système entre-temps.

Guide express : `docs/HUMAN_REVIEW_QUICKSTART.md` ; état gelé vérifiable : `docs/PHASE_4_FROZEN.md`.
