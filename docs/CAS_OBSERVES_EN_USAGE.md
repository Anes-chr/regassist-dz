# Cas observés en usage (à examiner par le juriste)

Réponses du système gelé `PHASE_4_FROZEN` jugées fausses ou trompeuses lors d'essais réels, **non corrigées dans le moteur** (le gel interdit de le modifier avant la validation humaine). Chaque cas dit ce qui a été observé, ce que contient réellement le corpus, et ce qui a été fait ou non. Les relectures ci-dessous sont celles d'une IA : **elles ne sont pas des avis juridiques**.

## Cas 1 — « C’est quoi l’allocation touristique ? » (18 octobre 2026)

**Réponse observée** (avec l'apostrophe typographique, ou en tapant seulement « allocation touristique ») :
> « L'allocation touristique est une allocation en devises attribuée aux nationaux résidents en voyage touristique ou d'affaires à l'étranger, en cas de décès du malade ou du national résidant… montant fixé à 50.000 Dinars [S3]. »
La même question avec une apostrophe droite et une minuscule (« c'est quoi l'allocation touristique ? ») donnait un refus ; la décision du moteur dépend de détails de saisie (apostrophe, casse).

**Pourquoi c'est faux.**
1. Les textes cités (Règlement n° 91-06 du 16 mai 1991, Règlement n° 92-10 du 17 novembre 1992, Instruction n° 83-92 du 27 décembre 1992) fixent des « allocations en devises à l'occasion d'hospitalisation et/ou de décès de nationaux à l'étranger » : il s'agit de l'**allocation de rapatriement de la dépouille mortelle**. « voyage touristique ou d'affaires » y décrit seulement la situation de la personne décédée.
2. L'expression « allocation touristique » ne figure dans **aucun passage** du corpus français (recherche exhaustive des 7 789 passages français).
3. Le montant cité (50 000 DA) est celui de 1992 ; l'Instruction n° 15-94 du 9 avril 1994 l'a porté à 75 000 DA, puis l'Instruction n° 25-95 du 19 avril 1995 à 110 700 DA. Le système avait signalé « modifié, peut-être plus à jour » dans les notes, mais le texte de la réponse l'affirme sans réserve.
4. La note « Correspondance partielle : vérifiez que ces passages répondent bien à votre question » était présente : l'alerte existe, la réponse reste assertive.

**Ce que dit le corpus sur le sujet réel** (relecture IA, à confirmer) : le régime correspondant est le « **droit de change pour voyage à l'étranger** » : Instruction n° 08-97 du 28 août 1997 (15 000 DA par an), abrogée par l'Instruction n° 05-2025 du 17 juillet 2025 (art. 12 ; 750 € / 300 €), elle-même abrogée par l'Instruction n° 07-2026 du 13 juillet 2026 (art. 21 ; effet le 19 juillet 2026 ; 750 € par an pour les 19 ans et plus, 300 € pour les 12 à moins de 19 ans dans la limite de 2 enfants par famille, séjour d'au moins 7 jours, carte de paiement internationale, Hadj exclu). **L'équivalence « allocation touristique » = « droit de change pour voyage à l'étranger » est l'usage courant, mais le corpus ne l'établit pas** : question au juriste.

**Mécanisme probable.** Seuls les textes de 1991-1995 réunissent les mots « allocation » et « touristique » ; les textes récents emploient « droit de change » et « voyage ». La recherche remonte donc les anciens textes (écart de vocabulaire, limite connue de la phase 2) ; le petit modèle rédige ensuite une définition en assemblant des fragments, sans vérifier que les passages définissent le terme.

**Mesure prise dans la couche d'accès (le moteur n'est pas modifié)** — voir `docs/LOCAL_DEPLOYMENT.md` § 19 : pour une question de définition explicite (« c'est quoi X », « qu'est-ce que X », « définition de X », « que signifie X »), si X ne figure dans aucun des textes retrouvés, la réponse est retirée et remplacée par « Le terme « X » n'apparaît dans aucun des textes retrouvés : je ne peux pas le définir à partir du corpus… ». Apostrophes et espaces typographiques sont ramenés à l'ASCII avant l'appel au moteur. Ces mesures ne font que transformer une réponse en refus.

**Restent non corrigés (à trancher avec le juriste).**
- L'assistant ne **répond** toujours pas correctement à « allocation touristique » : il ne sait pas que l'usage courant désigne le droit de change pour voyage. Une table d'équivalences d'usage (terme courant → terme du corpus) est possible dans la couche d'accès, mais elle pose une équivalence juridique : elle ne doit être écrite qu'après validation.
- Les questions qui ne sont **pas** des demandes de définition (« Quel est le montant de l'allocation touristique ? », « allocation touristique » seul) ne sont pas couvertes par le garde-fou.
- Le **montant périmé** (valeur d'origine d'un article ensuite modifié) reste possible : le moteur peut citer la version initiale d'un article sans les textes modificateurs.
- La décision de répondre ou de refuser reste instable près du seuil de similarité (casse, apostrophe, espaces).
