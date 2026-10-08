# Contrôle d'intégrité du corpus

Corpus : D:/llm/snapshots/corpus_2026-10-06

Synthèse : {'A_CORRIGER': 2, 'INFO': 3}

| Niveau | Type | n | Détail |
|---|---|---:|---|
| A_CORRIGER | texte_illisible | 115 | couche texte corrompue (lettres remplacées par des caractères de contrôle) ; ex. INS-01-26-20040513.ar::body-0, INS-02-26-20200429.ar::body-0, INS-03-24.ar::body-1::p1 |
| INFO | langue_incoherente | 1 | chunk dont l'écriture dominante contredit la langue annotée (tableaux bilingues, annexes) ; ex. LD-01-24.fr::annexe-N |
| A_CORRIGER | date_suspecte | 43 | l'année du numéro (ex. 01-2023) diffère de plus d'un an de la date enregistrée (ex. 2016-09-01 par défaut) ; ex. INS-09-16.fr, REG-02-04.fr, REG-02-05.fr |
| INFO | date_manquante | 21 | documents sans date ; ex.  |
| INFO | chunk_id_non_unique | 61 | mêmes identifiants (articles répétés dans un texte) : comparer par position, pas par identifiant ; ex. INS-04-19.fr::annexe-N::p1, INS-04-19.fr::annexe-N::p2, INS-04-19.fr::annexe-N |