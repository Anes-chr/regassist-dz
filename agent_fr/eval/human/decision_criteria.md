# Critères de décision GO / CONDITIONAL GO / NO-GO — fixés AVANT l'exécution du split TEST

Écrit le 2026-10-06, avant toute exécution du split TEST du benchmark `benchmark_v1`. Ces critères ne sont pas modifiés après la mesure (l'empreinte SHA-256 de ce fichier est
enregistrée dans `decision_criteria.md.sha256` et reprise dans `docs/RETRIEVAL_PHASE3.md`). Une seule métrique ne détermine jamais la décision : les critères sont cumulatifs.

## Définitions
* **Erreur temporelle critique** : pour une question dont la date de référence est « actuel », le système cite comme source une version listée dans `versions_interdites`
  (version remplacée, abrogée ou périmée) sans citer la version applicable — c'est-à-dire qu'il présente une ancienne valeur comme actuelle.
* **Hallucination (automatique)** : un nombre ou un numéro d'article de la réponse absent des sources données au modèle, ou un fait clé non soutenu par les sources citées.
* **Réponse correcte** : C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 (voir `bench.py`).
* **Hors corpus / hors sujet répondu** : question à refuser pour laquelle le système produit une réponse au lieu de refuser.
* **Validation humaine complète** : benchmark relu et validé par un juriste (`validation_humaine.statut ≠ en_attente` pour ≥ 90 % des items) ET ≥ 50 réponses évaluées par un humain.

## Décision
| Décision | Conditions (toutes) |
|---|---|
| **GO** (utilisation expérimentale) | validation humaine complète ; sur TEST : 0 erreur temporelle critique ; hallucination automatique ≤ 5 % des réponses rédigées ; refus corrects (hors corpus + hors sujet) ≥ 90 % ; réponse correcte ≥ 70 % des questions à réponse attendue ; aucune disposition de statut UNKNOWN présentée comme actuellement applicable sans signalement ; divergences humain/automatique documentées |
| **CONDITIONAL GO** | système local fonctionnel et sécurisé (aucune connexion sortante) ; sur TEST : erreurs temporelles critiques ≤ 10 % des questions « actuel » ; hallucination automatique ≤ 10 % ; refus corrects ≥ 80 % ; mais validation humaine absente ou partielle, ou un des critères GO non atteint de peu — dans ce cas la mention « à valider par un juriste » est obligatoire |
| **NO-GO** | l'un des cas suivants : > 10 % d'erreurs temporelles critiques sur les questions « actuel » ; hallucination automatique > 10 % ; refus corrects < 80 % ; une donnée du corpus quitte la machine ; la présence d'une erreur juridique critique non corrigeable sans fine-tuning ni nouvelle recherche |

## Règles de protocole
* Le split DEV sert à régler les règles de recherche/contexte ; chaque réglage fait à partir de DEV est listé dans `docs/RETRIEVAL_PHASE3.md`.
* Le split TEST est exécuté UNE fois, règles figées ; ses sorties brutes sont gelées (empreinte). Une correction humaine ultérieure du benchmark est appliquée par RE-NOTATION des sorties gelées, pas par ré-exécution.
* Aucune règle de notation n'est modifiée pour améliorer un score ; les divergences avec l'évaluation humaine sont documentées.
