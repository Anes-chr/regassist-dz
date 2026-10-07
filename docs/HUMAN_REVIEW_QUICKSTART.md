# Relecture juridique — guide express

**Statut du système : NO-GO PROVISOIRE** (validation humaine absente, TEST v2 absent). Votre relecture sert à décider de la suite ; elle ne « valide » pas le système à l'avance.

## Objectif

Vous n'avez **pas** à juger la qualité informatique du système. Pour chaque question et chaque réponse, vous dites si :

1. la **question** est juridiquement valide ;
2. la **source attendue** est correcte ;
3. l'**article attendu** est correct ;
4. la **réponse produite** est juridiquement correcte ;
5. la **version temporelle** (le texte applicable à la date visée) est correcte ;
6. la **citation** est correcte ;
7. la réponse contient une **hallucination** (une information qui n'est pas dans les sources).

« Ne sait pas » est toujours une réponse acceptable. Ne devinez pas.

## Ce que vous ouvrez (deux pages, hors ligne, double-clic)

| Page | Contenu | Ce que vous faites |
|---|---|---|
| `agent_fr/eval/human/review/benchmark_review_p4.html` | 130 questions, la réponse attendue (rédigée par une IA, **à valider**), la source officielle (lien vers le PDF) | pour chaque question : 5 oui / non / ne sait pas, puis **un classement** : CORRECT · INCORRECT · AMBIGU · QUESTION MAL FORMULÉE · SOURCE INCORRECTE · RÉPONSE ATTENDUE INCORRECTE |
| `agent_fr/eval/human/review/human_eval_p4.html` | 60 réponses du système avec les passages qu'il a reçus | 6 oui / non / ne sait pas (source, article, version, réponse, citation, justification) + **hallucination** : non · juridique · factuelle · métadonnée interne · ne sait pas |

* **Une question mal conçue n'est pas un échec du système** : classez-la (« question mal formulée », « ambiguë »…), elle sera comptée à part et jamais supprimée. Pour les questions volontairement ambiguës (type G), « AMBIGU » est la bonne réponse.
* **Métadonnée interne** : le modèle recopie parfois une date de référence fournie par le système (« au 31 décembre 1998 ») comme si elle venait des textes ; à vous de qualifier (hallucination ? métadonnée interne ?).
* Les réponses du système en arabe peuvent contenir des valeurs abîmées par l'OCR (« 902.75 % » pour « 2,75 % ») ; l'avertissement `OCR_UNCERTAIN` signale ce cas. Comparez au PDF officiel.
* Ouvrez le PDF officiel (lien dans la page) chaque fois que vous hésitez : c'est lui qui fait foi.

## Deux fiches à part (cas critiques et arbitrage)

* `docs/CAS_CRITIQUES_A_EXAMINER.md` + `review/cas_critiques_a_examiner.csv` — **H120** et **H129** (et rappel de H130) : sorties complètes avant / après, à qualifier (le CSV se remplit dans un tableur, séparateur « ; »).
* `docs/ARBITRAGE_JUMEAUX_FR_AR.md` + `review/arbitrage_jumeaux_fr_ar.csv` — **REG-90-01, REG-02-01, REG-06-01** : le français et l'arabe portent des dates différentes ; **personne n'a choisi** ; vous arbitrez.
* Annuaire des 1 085 documents avec leur URL officielle : `review/corpus_index_for_jurist.csv`.

## Enregistrer son travail

* La page garde vos réponses **dans le navigateur** (même ordinateur, même navigateur, même fichier). Cliquez régulièrement sur **« Exporter les verdicts (JSON) »** : le fichier exporté est votre sauvegarde (indiquez votre nom quand il est demandé).
* Transmettez les fichiers exportés et les deux CSV remplis. Ils sont enregistrés tels quels (ajout seul, rien n'est réécrit, aucune de vos réponses ne change une règle du système) :
  `python -m agent_fr.eval.human.annotations ingest --file <export.json>` puis `ingest-sheet --file <fiche.csv>`.
* Ne rouvrez pas une page régénérée à la place de l'ancienne : un autre horodatage = un autre espace de stockage dans le navigateur. Les deux pages officielles ne sont pas régénérées.

## Ensuite

Quand vous êtes disponible, vous pourrez aussi **rédiger TEST v2** : domaines, questions, réponses attendues, sources, articles, dates de référence ; validation du jeu ; transmission du jeu final. Gabarit : `python -m agent_fr.eval.human.test_v2 author-template`.
Écrivez-les **sans consulter les réponses du système** : c'est ce qui rend le test indépendant. Une fois le jeu validé et gelé, il n'est exécuté qu'une seule fois.

## Confidentialité

Tout reste sur cette machine : pages hors ligne, aucun envoi. Ne publiez pas ces fichiers sur un service tiers (ils contiennent des extraits du corpus).
