# Constats pour relecture juridique — corpus français Banque d'Algérie

> Généré par un assistant IA (Claude). **Ce n'est pas une validation par un juriste humain** : chaque constat est une piste à confirmer sur le PDF officiel.

## 1. Traçabilité des citations
- 7596 passages non-OCR vérifiés contre les PDF d'origine : **7570 identiques à la page annoncée**, 26 avec une différence en bordure (césure / en-tête), 0 introuvables.
- 189 passages issus d'OCR **non vérifiables automatiquement** : contrôle humain requis.
- La « page » citée est la **page du PDF** (pas la pagination imprimée du texte, ex. loi 23-09 : page PDF 12 = page imprimée 7).

## 2. Textes évolutifs (modifiés / abrogés par d'autres textes du corpus)
- Textes ayant au moins une modification/abrogation connue : modifiés 77, complétés 56, abrogés 91, remplacés 30.
- Statut « abrogé » affirmé (preuve dans l'intitulé d'un texte officiel) : 2. Tous les autres : « STATUT À VÉRIFIER ». **Le site ne publie aucun statut de vigueur.**
- Références à des textes absents du corpus (relations non résolues) : 33 — un texte cité mais non collecté peut en modifier un autre.
- **Risque principal** : une question simple peut tomber sur la version d'origine d'un texte modifié (ex. plafond de garantie des dépôts : 600 000 DA en 2004, 2 000 000 DA depuis 2018/2020). L'agent affiche alors une alerte et remonte le texte modificateur ; ce mécanisme dépend de la détection des relations (voir §5).

## 3. Incohérences entre le libellé du site et le document
29 documents. Le pipeline conserve les deux valeurs, sans correction silencieuse.

| Document | Libellé du site | Document (en-tête) | Champ |
|---|---|---|---|
| INS-01-22.fr | 2022-01-03 | 2022-01-05 | date |
| INS-01-96.fr | 02-96 | 01-96 | numero |
| INS-01-96.fr | 1996-02-06 | 1996-01-09 | date |
| INS-02-17.fr~2 | 02-2016 | 02-2017 | numero |
| INS-06-20-20200429.fr | 2004-05-13 | 2020-04-29 | date |
| INS-06-20-20200429.fr~2 | 2004-05-13 | 2020-04-29 | date |
| INS-27-91.fr | 1991-10-01 | 1991-04-21 | date |
| NOT-001-DGC-BA-07.fr | 001-DGC-ba-2007 | 001-DGC-BA-2007 | numero |
| NOT-001-vga.hi-17.fr | 001-VGA.Hi-2017 | 001-vga.hi-2017 | numero |
| NOT-002-01.fr | 02-2001 | 002-2001 | numero |
| NOT-002-vga.hi-17.fr | 002-VGA.Hi-2017 | 002-vga.hi-2017 | numero |
| NOT-11-DGC-09.fr | 11-DGC-BA-2009 | 11-DGC-2009 | numero |
| NOT-144-DGC-09.fr | 144-DGC-BA-2009 | 144-DGC-2009 | numero |
| NOT-16-DGC-09.fr | 16-DGC-BA-2009 | 16-DGC-2009 | numero |
| NOT-164-DGC-09.fr | 164-DGC-BA-2009 | 164-DGC-2009 | numero |
| NOT-165-DGC-09.fr | 165-DGC-BA-2009 | 165-DGC-2009 | numero |
| NOT-166-DGC-09.fr | 166-DGC-BA-2009 | 166-DGC-2009 | numero |
| NOT-167-DGC-09.fr | 167-DGC-BA-2009 | 167-DGC-2009 | numero |
| NOT-180-DGC-09.fr | 180-DGC-BA-2009 | 180-DGC-2009 | numero |
| NOT-186-19.fr | 186 | 186-2019 | numero |
| NOT-210-DGC-09.fr | 210-DGC-BA-2009 | 210-DGC-2009 | numero |
| ORD-09-01-20030826.fr | 2009-07-22 | 2003-08-26 | date |
| REG-02-04.fr | 2003-01-09 | 1991-08-14 | date |
| REG-02-05.fr | 2002-12-31 | 1997-04-06 | date |
| REG-11-06-20111019.fr | 2007-02-03 | 2011-10-19 | date |
| REG-26-02.fr | 2007-02-03 | 2026-07-23 | date |
| REG-91-03.fr | 91-02 | 91-03 | numero |
| REG-94-10-19940412.fr | 1994-04-13 | 1994-04-12 | date |
| REG-94-11-19940412.fr | 1994-04-13 | 1994-04-12 | date |
| REG-97-04.fr | 97-01 | 97-04 | numero |

## 4. Textes en double (deux fichiers pour le même texte) : différences de CHIFFRES
114 textes présents en deux fichiers (chemins `/2021/…` et `/2023/…`). Classés par nombre de chiffres divergents :

| Texte | Fichiers | Similarité | Chiffres qui diffèrent |
|---|---|---|---|
| INS-07-11 | INS-07-11.fr / INS-07-11.fr~2 | 97% | 15%, 20%, 25%, 30%, 50%, 5001 |
| INS-05-21 | INS-05-21.fr / INS-05-21.fr~2 | 83% | 9181039919 |
| INS-02-10 | INS-02-10.fr / INS-02-10.fr~2 | 87% | 2222 |
| REG-05-02-20050305 | REG-05-02-20050305.fr / REG-05-02-20050305.fr~2 | 94% | 88,89 |
| INS-02-16 | INS-02-16.fr / INS-02-16.fr~2 | 99% | 1501 |
| REG-02-03 | REG-02-03.fr / REG-02-03.fr~2 | 99% | 9109 |
| REG-07-01-20070203 | REG-07-01-20070203.fr / REG-07-01-20070203.fr~2 | 100% | 0311 |
| INS-04-10-20101215 | INS-04-10-20101215.fr / INS-04-10-20101215.fr~2 | 91% | — |
| INS-02-04 | INS-02-04.fr / INS-02-04.fr~2 | 91% | — |
| REG-94-10-19940412 | REG-94-10-19940412.fr / REG-94-10-19940412.fr~2 | 91% | — |
| REG-95-01 | REG-95-01.fr / REG-95-01.fr~2 | 91% | — |
| REG-95-02-19950228 | REG-95-02-19950228.fr / REG-95-02-19950228.fr~2 | 91% | — |
| INS-03-12 | INS-03-12.fr / INS-03-12.fr~2 | 91% | — |
| INS-01-09 | INS-01-09.fr / INS-01-09.fr~2 | 92% | — |
| REG-91-01 | REG-91-01.fr / REG-91-01.fr~2 | 92% | — |
| INS-03-09 | INS-03-09.fr / INS-03-09.fr~2 | 93% | — |
| INS-01-12-20120429 | INS-01-12-20120429.fr / INS-01-12-20120429.fr~2 | 93% | — |
| INS-06-09 | INS-06-09.fr / INS-06-09.fr~2 | 93% | — |
| REG-94-11-19940412 | REG-94-11-19940412.fr / REG-94-11-19940412.fr~2 | 93% | — |
| INS-02-21-20210207 | INS-02-21-20210207.fr / INS-02-21-20210207.fr~2 | 94% | — |
| INS-07-20 | INS-07-20.fr / INS-07-20.fr~2 | 94% | — |
| REG-91-05 | REG-91-05.fr / REG-91-05.fr~2 | 94% | — |
| INS-03-17 | INS-03-17.fr / INS-03-17.fr~2 | 94% | — |
| REG-93-02 | REG-93-02.fr / REG-93-02.fr~2 | 94% | — |
| INS-01-13 | INS-01-13.fr / INS-01-13.fr~2 | 94% | — |

107/114 paires n'ont aucun chiffre significatif divergent (différences probablement typographiques ou de mise en page).

## 4 bis. Documents signalés pour contrôle humain
- `meme_texte_plusieurs_fichiers` : 228
- `incoherence_libelle_vs_document` : 30
- `numerotation` : 19
- `ocr_utilise_verification_humaine` : 17
- `ocr_faible_confiance` : 7
- `aucun_article_detecte` : 7
- `metadonnees_incompletes` : 5
- `texte_identique_a_un_autre_fichier` : 4

## 5. Limites de l'automatisation à faire confirmer
- Les relations (modifie / abroge / complète / remplace) sont extraites par motifs lexicaux : l'intitulé donne une preuve forte, le corps du texte une preuve à vérifier. Une abrogation implicite (« toutes dispositions contraires ») n'est pas résolue.
- Un texte « abrogé par » un autre peut l'être partiellement : le drapeau `partial` existe mais sa fiabilité n'est pas mesurée.
- Les copies `/2021/` et `/2023/` : le corpus ne dit pas laquelle fait foi.
- Les questions de test (`agent_fr/eval/gold_v2.jsonl`) sont relues par un assistant IA, pas par un juriste : champ `validated_by`.
