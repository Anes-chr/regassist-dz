# Contrôle d'intégrité du corpus

Corpus : corpus vivant

Synthèse : {'A_CORRIGER': 3, 'INFO': 3}

| Niveau | Type | n | Détail |
|---|---|---:|---|
| A_CORRIGER | documents_en_echec | 38 | documents non extraits ou non téléchargés (voir failed_documents.json) ; ex. https://www.bank-of-algeria.dz/pdf/instructions1990/instruction0690.pdf, https://www.bank-of-algeria.dz/pdf/instructions1995/instruction7895.pdf, https://www.bank-of-algeria.dz/pdf/instructions1995/instruction7995.pdf |
| A_CORRIGER | texte_illisible | 5 | couche texte corrompue (lettres remplacées par des caractères de contrôle) ; ex. INS-06-21.ar::annexe-1, LD-02-24.ar::body-0::p1, LD-02-24.ar::body-0::p2 |
| INFO | langue_incoherente | 1 | chunk dont l'écriture dominante contredit la langue annotée (tableaux bilingues, annexes) ; ex. LD-01-24.fr::annexe-N |
| A_CORRIGER | date_suspecte | 4 | l'année du numéro (ex. 01-2023) diffère de plus d'un an de la date enregistrée (ex. 2016-09-01 par défaut) ; ex. REG-20-01-20220131.fr, NOT-02-24-20160901.fr, NOT-01-26.fr |
| INFO | date_manquante | 27 | documents sans date ; ex.  |
| INFO | chunk_id_non_unique | 76 | mêmes identifiants (articles répétés dans un texte) : comparer par position, pas par identifiant ; ex. INS-04-19.fr::annexe-N::p1, INS-04-19.fr::annexe-N::p2, INS-04-19.fr::annexe-N |