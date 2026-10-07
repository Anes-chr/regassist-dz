# Relecture humaine — mode d'emploi pour le juriste

> **Phase 5 (gel de validation)** : guide express d'une page : [HUMAN_REVIEW_QUICKSTART.md](HUMAN_REVIEW_QUICKSTART.md) ; note de présentation : [NOTE_AU_JURISTE.md](NOTE_AU_JURISTE.md) ; cas H120 / H129 :
> [CAS_CRITIQUES_A_EXAMINER.md](CAS_CRITIQUES_A_EXAMINER.md) ; trois conflits de dates FR/AR : [ARBITRAGE_JUMEAUX_FR_AR.md](ARBITRAGE_JUMEAUX_FR_AR.md). Les deux interfaces officielles sont
> `review/benchmark_review_p4.html` et `review/human_eval_p4.html` (non régénérées : l'horodatage fixe l'espace de stockage de vos réponses dans le navigateur). Statut : **NO-GO PROVISOIRE**.

Deux relectures sont demandées. Aucune n'envoie de donnée : ce sont des **fichiers HTML locaux** qui s'ouvrent dans un navigateur, sans réseau ; les réponses sont enregistrées dans
le navigateur puis exportées dans un fichier JSON que vous transmettez.

## 1. Valider le benchmark (≈ 135 questions)

Fichier : `agent_fr/eval/human/review/benchmark_review.html` (et `benchmark_review.csv` pour un tableur).
Les questions, les réponses attendues et les passages ont été **rédigés par une IA** (Claude) à partir des textes officiels du corpus de la Banque d'Algérie ; chaque citation de passage
est vérifiée mécaniquement dans le corpus, mais **le choix des questions, la réponse attendue et l'état juridique n'ont jamais été validés par un humain**.

Pour chaque question, répondez :

| Champ | Question à vous poser |
|---|---|
| Question claire | La question est-elle compréhensible, non ambiguë (sauf les questions volontairement ambiguës de type G) ? |
| Source / article / passage | Le texte, l'article et la citation indiqués répondent-ils bien ? Les liens ouvrent le PDF officiel et la page du site. |
| Réponse attendue | Est-elle juridiquement exacte ? Sinon, saisissez la bonne réponse. |
| État juridique et date de référence | Le texte est-il applicable / modifié / remplacé / abrogé / périmé à la date indiquée ? Statuts : ACTIVE, MODIFIED, REPLACED, ABROGATED, HISTORICAL, UNKNOWN. En cas de doute : UNKNOWN. |
| Verdict | valider · valider avec corrections · rejeter |

Points d'attention particuliers :
* **Séries annuelles** (prime du fonds de garantie des dépôts, seuils semestriels des taux excessifs) : chaque instruction fixe la valeur d'**une période** (« exercice 2012 ») ; elle n'abroge pas la précédente.
  Les questions utilisent la période, pas l'année de signature.
* **Questions « actuel »** : le site ne publie aucun statut de vigueur ; « actuel » signifie « version la plus récente du corpus » (le corpus peut être incomplet).
* Ne corrigez pas la question pour qu'elle « passe » : signalez un défaut de la question, pas du système.

Retour : bouton **Exporter** de la page → fichier `verdicts_benchmark_review.json`. Il est intégré par
`python -m agent_fr.eval.human.packs ingest-review --bench benchmark_v1.jsonl --verdicts verdicts_benchmark_review.json` (l'historique des corrections est conservé).

## 2. Évaluer 60 réponses du système

Fichier : `agent_fr/eval/human/review/human_eval.html` (généré après l'exécution du benchmark). Pour chaque réponse, six oui/non :
**Source correcte · Article correct · Version correcte · Réponse correcte · Citation correcte · Hallucination**, plus un commentaire libre.
Vous voyez la réponse, les passages donnés au modèle et le statut calculé ; la « réponse attendue » (non validée) est repliée : consultez-la en dernier.

Retour : `verdicts_human_eval.json`, intégré par `... packs ingest-eval` : accord avec la notation automatique, coefficient kappa, liste des divergences.
**Les règles de notation automatique ne sont jamais modifiées pour rapprocher les scores** : les divergences sont documentées.

## Phase 4 — schéma complet et enregistrement sans interprétation

**Utilisez de préférence les fichiers `*_p4.html`** (mêmes questions, mêmes 60 réponses que ceux de la phase 3, qui restent **inchangés** à côté) :
`agent_fr/eval/human/review/benchmark_review_p4.html` (et `.csv`) et `agent_fr/eval/human/review/human_eval_p4.html`. Aucun score automatique n'y est affiché.

**Benchmark (130 questions)** : pour chaque question, répondez oui / non / ne sait pas à (1) question correcte ? (2) source attendue correcte ? (3) article attendu correct ? (4) réponse attendue correcte ?
(5) date de référence correcte ? puis classez la question : **CORRECT · INCORRECT · AMBIGU · QUESTION MAL FORMULÉE · SOURCE INCORRECTE · RÉPONSE ATTENDUE INCORRECTE**.
Une question mal conçue n'est **pas** comptée comme un échec du système (elle est listée à part, jamais supprimée) ; pour une question de type G (ambiguë à dessein), « AMBIGU » est la bonne réponse.

**Réponses (60)** : (1) source ? (2) article ? (3) version juridique ? (4) réponse ? (5) citation ? (6) réponse suffisamment justifiée par les sources citées ? (7) hallucination : **non / oui juridique / oui factuelle /
information venant d'une métadonnée interne du système / ne sait pas**. La « métadonnée interne » est la date de référence de la consigne que le modèle recopie comme si elle venait des sources (4 cas relevés par l'IA, non tranchés) :
c'est à vous de la qualifier ; elle est présentée à part et n'entre pas dans le taux d'hallucination humaine.

**Enregistrement** (bouton « Exporter » → fichier `.json`, puis, sur cette machine) :

```
python -m agent_fr.eval.human.annotations ingest --file verdicts_benchmark_review_p4.json
python -m agent_fr.eval.human.annotations ingest --file verdicts_human_eval_p4.json
python -m agent_fr.eval.human.annotations report
```

* Les annotations sont **ajoutées** à `agent_fr/eval/human/annotations/*.jsonl` (évaluateur, date, empreintes) ; un export déjà intégré, une valeur hors liste, un identifiant inconnu ou un évaluateur non nommé sont refusés.
* Le benchmark (`benchmark_v1_draft.jsonl`, qui contient TEST v1), les sorties gelées et les règles de notation ne sont **jamais réécrits** (`verify_frozen.py` le contrôle). L'ancienne commande `packs ingest-review`, qui réécrivait le benchmark, refuse désormais ce fichier.
* **Aucune annotation n'est transformée en règle de recherche, de contexte ou de notation.** Le rapport (`human_validation_report.md/.json`) présente séparément : hallucination juridique, hallucination factuelle, métadonnée interne,
  réponse correcte mais notation automatique incorrecte (et l'inverse), questions à ne pas compter comme échec du modèle ; il compare le taux d'hallucination humaine au seuil pré-enregistré **sans le modifier**.
* « Validation humaine complète » (critères de décision) = au moins 90 % du benchmark annoté **et** au moins 50 réponses évaluées.

**Trois arbitrages de jumeaux FR/AR** (`boa_pipeline/twin_overrides.json`, champ `proposals`) : REG-90-01, REG-02-01 et REG-06-01 ont un texte arabe et un texte français de même numéro mais de dates complètes différentes ; l'IA ne tranche pas.
Si, après lecture des deux PDF, vous confirmez qu'il s'agit du même texte, renseignez `confirmed_by` dans `confirmed` (jamais ailleurs) puis relancez `python -m boa_pipeline build`.

**TEST v2** : ne sera créé qu'après votre validation. Les questions doivent être **rédigées par un juriste** (gabarit : `python -m agent_fr.eval.human.test_v2 author-template`) sans consulter les réponses du système ;
le fichier est ensuite contrôlé (`validate`), gelé (`freeze`) et exécuté une seule fois (`run`, verrou).

## Fiches complémentaires (phase 5)

Deux fiches CSV (séparateur « ; », à ouvrir dans un tableur) se remplissent à côté des deux pages : `review/cas_critiques_a_examiner.csv` (H120, H129, H130 ; qualification : erreur juridique critique, non critique,
réponse hors sujet, refus à tort, refus attendu, non-erreur, autre — commentaire obligatoire pour « autre ») et `review/arbitrage_jumeaux_fr_ar.csv` (FR / AR / DEUX_TEXTES_DISTINCTS / INDETERMINE ;
commentaire obligatoire pour les deux derniers). Enregistrement : `python -m agent_fr.eval.human.annotations ingest-sheet --file <fiche.csv>` (ajout seul, valeurs contrôlées, jamais appliqué automatiquement au corpus).

## Confidentialité

* Les pages sont générées localement (`agent_fr/eval/human/review/`) et ne chargent aucune ressource externe.
* Le corpus reste sur cette machine. Ne publiez pas ces pages sur un service tiers (document de travail contenant des extraits du corpus).
