# Arbitrage humain : trois textes arabes / français en conflit de dates

**Statut du système : NO-GO PROVISOIRE.** Pour ces trois textes, le français et l'arabe portent des **dates complètes différentes**. L'IA **ne choisit ni la date française ni la date arabe** : les deux documents restent des textes distincts dans le corpus tant que vous n'avez pas arbitré. Rien dans le pipeline n'applique votre décision automatiquement : elle se matérialise par une saisie explicite dans `boa_pipeline/twin_overrides.json` (champ `confirmed`, `confirmed_by` renseigné) puis une reconstruction.

Fiche de réponse : `agent_fr/eval/human/review/arbitrage_jumeaux_fr_ar.csv` (enregistrement : `python -m agent_fr.eval.human.annotations ingest-sheet --file <fiche.csv>`).

## REG-90-01

| | Français | Arabe |
|---|---|---|
| Document | REG-90-01-19900704.fr | REG-90-01-19900604.ar |
| Intitulé du site | Règlement n° 90-01 du 4 juillet 1990 relatif au capital minimum des banques et établissements financiers exerçant en Algérie. | نظام رقم 90-01 المؤرخ في 4 يونيو 1990، يتعلق بالحد الأدنى لرأسمال البنوك والمؤسسات المالية العاملة في الجزائر. |
| **Date** | **1990-07-04** (source : en-tête du document) | **1990-06-04** (source : libelle) |
| Source (PDF officiel) | https://www.bank-of-algeria.dz/stoodroa/2022/04/reglement9001-1.pdf | https://www.bank-of-algeria.dz/stoodroa/2023/02/01-90.pdf |
| Page du site qui le liste | https://www.bank-of-algeria.dz/importations-exportations-reglement/ | https://www.bank-of-algeria.dz/ar/%d8%b4%d8%b1%d9%88%d8%b7-%d8%aa%d8%a3%d8%b3%d9%8a%d8%b3-%d9%88-%d8%a5%d9%86%d8%b4%d8%a7%d8%a1-%d8%a7%d9%84%d8%a8%d9%86%d9%88%d9%83-%d9%88-%d8%a7%d9%84%d9%85%d8%a4%d8%b3%d8%b3%d8%a7%d8%aa-%d8%a7%d9%84/ |
| Fichier local / pages / extraction | `corpus/raw/178a43acfa12__reglement9001-1.pdf` / 2 / pdf_text | `corpus/raw/0239a46a405e__01-90.pdf` / 1 / ocr |

**Raison du conflit** : libellé et texte arabes : 4 يونيو (4 juin) 1990 ; texte français : 4 juillet 1990.

Éléments factuels (relevés par l'IA, non conclusifs) :
* Même type, même numéro, même objet (capital minimum). Le PDF arabe imprime aussi une date hégirienne (12 Dhou al-Hijja 1410) ; au calendrier tabulaire (± 2 jours) elle correspond au 4-6 juillet 1990. Cette conversion est un indice de cohérence, pas une preuve, et ne tranche pas.
* Éléments qui s'y opposent : dates grégoriennes explicites différentes dans les deux PDF.
* En-tête du PDF français (début du texte extrait) : « REGLEMENT N°90-01 DU 4 JUILLET 1990 RELATIF AU CAPITAL MINIMUM DES BANQUES ET ETABLISSEMENTS FINANCIERS EXERCANT EN ALGERIE Le Gouverneur de la Banque d'Algérie, - Vu la loi n°90-10 du 14 avril 1990 relative à la monnaie et au crédit, notamment les articles […] »
* En-tête du PDF arabe (début du texte extrait par OCR) : « نظام رقم 90 - 01 مؤرخ في 12 ذي الحجة عام 1410 الموافق 4 يونيو سنة 1990 يتعلق بالحد الادنى لراسمال البنوك والمؤسسسات المالية العاملة في الجزائر ان محافظ البنك الجزائري. - بمقتخى القانون رقم 90 - 10 المؤرخ à‏ 19 رمخسان عام 1410 الموافق 14 افريل سنة 1990 المتعلق […] »
* Date hégirienne imprimée dans le PDF arabe : 12/12/1410 H ; au calendrier tabulaire (± 2 jours) : 1990-07-06. À vérifier avec un convertisseur de référence.

**Votre arbitrage** : la date de référence est-elle celle du français, celle de l'arabe, s'agit-il de **deux textes distincts**, ou est-ce **indéterminé** ? (colonnes `reference_correcte` : FR / AR / DEUX_TEXTES_DISTINCTS / INDETERMINE ; commentaire obligatoire pour les deux dernières.)

## REG-02-01

| | Français | Arabe |
|---|---|---|
| Document | REG-02-01-20020217.fr | REG-02-01-20020220.ar |
| Intitulé du site | Règlement n°2002-01 du 17 février 2002 fixant les conditions de constitution de dossier de demande d’autorisation d’investissement et/ou […] | نظام رقم 02-01 المؤرخ في 20 فبراير 2002، يحدد شروط تكوين ملف خاص بطلب الترخيص بالاستثمار و/او إقامة مكتب في […] |
| **Date** | **2002-02-17** (source : en-tête du document) | **2002-02-20** (source : libelle) |
| Source (PDF officiel) | https://www.bank-of-algeria.dz/stoodroa/2021/03/reglement200201.pdf | https://www.bank-of-algeria.dz/stoodroa/2023/02/01-02-1.pdf |
| Page du site qui le liste | https://www.bank-of-algeria.dz/reglement-2003/ | https://www.bank-of-algeria.dz/ar/%d8%aa%d9%86%d8%b8%d9%8a%d9%85-%d8%a7%d9%84%d8%b5%d8%b1%d9%81-2/ |
| Fichier local / pages / extraction | `corpus/raw/e9907885fcc9__reglement200201.pdf` / 3 / pdf_text | `corpus/raw/fdecda337760__01-02-1.pdf` / 2 / ocr |

**Raison du conflit** : libellé arabe : 20 février 2002 ; texte français : 17 février 2002 ; date du texte arabe illisible à l'OCR (« 8 ذي ا … »).

Éléments factuels (relevés par l'IA, non conclusifs) :
* Même type, même numéro, même objet.
* Éléments qui s'y opposent : dates grégoriennes différentes de 3 jours ; date hégirienne du PDF arabe illisible.
* En-tête du PDF français (début du texte extrait) : « REGLEMENT N°2002-01 DU 17 FEVRIER 2002 FIXANT LES CONDITIONS DE CONSTITUTION DE DOSSIER DE DEMANDE D'AUTORISATION D'INVESTISSEMENT ET/OU D'INSTALLATION DE BUREAU DE REPRESENTATION A L'ETRANGER DES OPERATEURS ECONOMIQUES DE DROIT ALGERIEN Le Gouverneur de la […] »
* En-tête du PDF arabe (début du texte extrait par OCR) : « نظام رقم 01-02 مؤرخ في 8 ذي ا La ml‏ 2,؛: يهدد شروط تكوين ملّف للقانون الجزائري. إن محافظ بنك الجزائر», - بمقتضى القانون رقم 10-90 المؤرخ في 19 والمتعلق بالنقد والقرضء لا سيما المواد 43 مكرر , 4 4. الفقرتان طواك و187 مثه, - وبمقتضى الأمر رقم 75- 59 المؤرّخ في […] »

**Votre arbitrage** : la date de référence est-elle celle du français, celle de l'arabe, s'agit-il de **deux textes distincts**, ou est-ce **indéterminé** ? (colonnes `reference_correcte` : FR / AR / DEUX_TEXTES_DISTINCTS / INDETERMINE ; commentaire obligatoire pour les deux dernières.)

## REG-06-01

| | Français | Arabe |
|---|---|---|
| Document | REG-06-01-20060907.fr | REG-06-01-20060514.ar |
| Intitulé du site | Règlement n°2006-01 du 7 septembre portant frappe et émission d’une pièce de monnaie métallique de dix (10) dinars en argent. | ظام رقم 06-01 المؤرخ في 14 مايو 2006، يتضمن سك قطعة نقدية معدنية قيمتها عشرة (10) دنانير فضية وإصدارها. |
| **Date** | **2006-09-07** (source : en-tête du document) | **2006-05-14** (source : libelle) |
| Source (PDF officiel) | https://www.bank-of-algeria.dz/stoodroa/2022/04/reglement200601.pdf | https://www.bank-of-algeria.dz/stoodroa/2023/02/01-06.pdf |
| Page du site qui le liste | https://www.bank-of-algeria.dz/reglement-piece-de-monnaie/ | https://www.bank-of-algeria.dz/ar/%d8%a5%d9%86%d8%b4%d8%a7%d8%a1-%d8%a5%d8%b5%d8%af%d8%a7%d8%b1-%d9%88-%d8%aa%d8%af%d8%a7%d9%88%d9%84-%d8%a7%d9%84%d9%82%d8%b7%d8%b9-%d8%a7%d9%84%d9%86%d9%82%d8%af%d9%8a%d8%a9-%d8%a7%d9%84%d9%85%d8%b9/ |
| Fichier local / pages / extraction | `corpus/raw/672cc8e72f57__reglement200601.pdf` / 2 / pdf_text | `corpus/raw/1773a156b336__01-06.pdf` / 1 / ocr |

**Raison du conflit** : libellé et texte arabes : 14 mai 2006 (16 Rabi' II 1427) ; texte français : « 07 septembre » (année absente de l'en-tête).

Éléments factuels (relevés par l'IA, non conclusifs) :
* Même type, même numéro, même objet (pièce de 10 dinars en argent).
* Éléments qui s'y opposent : date différente de plus de trois mois ; année absente de l'en-tête français.
* En-tête du PDF français (début du texte extrait) : « REGLEMENT N°2006-01 DU 07 SEPTEMBRE PORTANT FRAPPE ET ÉMISSION D’UNE PIÈCE DE MONNAIE MÉTALLIQUE DE DIX (10) DINARS EN ARGENT Le Gouverneur de la Banque d'Algérie, - Vu l’Ordonnance n°03-11 du 26 août 2003, relative à la Monnaie et au Crédit notamment ses […] »
* En-tête du PDF arabe (début du texte extrait par OCR) : « نظام رقم 06 -01 مؤرخ في 16 ربيع الثاني عام 7 الموافق 14 مليى سنة 2006. يتضمن سك قطعة نقدية معدنية قيمتها عشرة )10( دنانير فضية وإصدارها. إن محافظ بنك الجزائرء ع س . - بمقتضى الأمسر رقم 03 - 11 الموّرخ في 27 جمادى التانية عام 1424 الموافق 26 شت سنة 2003 […] »
* Date hégirienne imprimée dans le PDF arabe : 16/4/1427 H ; au calendrier tabulaire (± 2 jours) : 2006-05-15. À vérifier avec un convertisseur de référence.

**Votre arbitrage** : la date de référence est-elle celle du français, celle de l'arabe, s'agit-il de **deux textes distincts**, ou est-ce **indéterminé** ? (colonnes `reference_correcte` : FR / AR / DEUX_TEXTES_DISTINCTS / INDETERMINE ; commentaire obligatoire pour les deux dernières.)

