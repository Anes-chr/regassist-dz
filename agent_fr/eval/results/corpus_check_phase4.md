# Contrôle d'intégrité du corpus

Corpus : D:/llm/snapshots/corpus_phase4

Synthèse : {'A_CORRIGER': 2, 'INFO': 5}

| Niveau | Type | n | Détail |
|---|---|---:|---|
| A_CORRIGER | texte_illisible | 10 | couche texte corrompue (lettres remplacées par des caractères de contrôle) ; ex. INS-01-23.ar::preamble-0, INS-06-21.ar::annexe-1, INS-NA-2619a04e.ar::preamble-0 |
| INFO | langue_incoherente | 1 | chunk dont l'écriture dominante contredit la langue annotée (tableaux bilingues, annexes) ; ex. LD-01-24.fr::annexe-01 |
| A_CORRIGER | date_suspecte | 2 | l'année du numéro (ex. 01-2023) diffère de plus d'un an de la date enregistrée (ex. 2016-09-01 par défaut) ; ex. REG-20-01-20220131.fr, REG-20-01-20260514.fr |
| INFO | date_manquante | 20 | documents sans date ; ex.  |
| INFO | jumeau_ar_conflit_de_date | 3 | même type + même numéro qu'un texte français mais dates complètes différentes : NON tranché automatiquement (proposition dans boa_pipeline/twin_overrides.json, arbitrage humain) ; ex. REG-02-01-20020220.ar, REG-06-01-20060514.ar, REG-90-01-19900604.ar |
| INFO | lien_deplace | 19 | ancien chemin du site /pdf/… ; le même fichier est dans le corpus sous son URL officielle actuelle (pas un document manquant) ; ex. https://www.bank-of-algeria.dz/pdf/instructions1990/instruction0690.pdf, https://www.bank-of-algeria.dz/pdf/instructions1995/instruction7895.pdf, https://www.bank-of-algeria.dz/pdf/instructions1995/instruction7995.pdf |
| INFO | ocr_uncertain | 80 | chunks arabes (OCR) dont une valeur numérique n'est pas corroborée par le texte français : signalés, jamais corrigés ; ex. INS-01-12.ar, INS-01-15.ar, INS-01-16.ar |