# Cas critiques à examiner attentivement

**Statut du système : NO-GO PROVISOIRE** (validation humaine absente, TEST v2 absent). Ces cas **ne sont corrigés ni automatiquement ni à la main** : ils sont soumis au juriste et au benchmark indépendant. Les observations « techniques » ci-dessous sont celles d'une IA (non humaine) et ne préjugent d'aucune qualification juridique.

Les deux cas ne figurent **pas** dans l'échantillon des 60 réponses de `human_eval_p4.html` (la phase 3 refusait de répondre à H120 et H129 n'a pas été tiré) : c'est pourquoi leurs sorties complètes sont reproduites ici. Fiche de réponse : `agent_fr/eval/human/review/cas_critiques_a_examiner.csv` (à renvoyer remplie ; enregistrement : `python -m agent_fr.eval.human.annotations ingest-sheet --file <fiche.csv>`).

## H120 — compte en devises « débiteur » (question en arabe)

**Question** (J_fr_ar, difficulté moyen, langue ar) : هل يمكن أن تكون الحسابات بالعملة الصعبة المفتوحة باسم الأشخاص المذكورين مدينة؟

**Attendu (rédigé par une IA, non validé)** : REG-09-01 article 4 ; date de référence : aucune ; statut attendu : non précisé
* Réponse attendue : لا، يجب أن تعمل هذه الحسابات حصرا في وضعية دائنة ولا يمكن أن تكون مدينة بأي حال.
* Passage attendu (texte français officiel) : « ne peuvent en aucun cas présenter un solde débiteur » — Les comptes devises ouverts au nom des personnes visées à l’article 1er ci-dessus doivent fonctionner exclusivement en situation créditrice et ne peuvent en aucun cas présenter un solde débiteur.

**Évolution** : *avant la correction du parsing* (phase 3) → **refus à tort** ; *après la correction* (phase 4) → **réponse hors sujet** (voir ci-dessous).

### Phase 3 (sortie gelée `human_bench_dev_final2.json`)

* Réponse : « Je ne trouve pas de disposition correspondante dans le corpus disponible. »
* Passages cités : aucun ; rang du passage attendu dans la recherche : 1
* Notes du système : aucune
* Notation automatique : réponse correcte = False ; refus à tort = True ; hallucination = False ; erreur temporelle critique = None ; statut correct = None
* Passages donnés au modèle :
* **[S1]** REG-09-01, article 4 — statut calculé par le système : UNKNOWN
  > يجب .أن تكون الحسابات بالعملة الصعبة المفتوحة بساسم ا لأشخاض المذكورين فى المدة الأولى أعلاه. في وهسعيسة دائئة Mai‏ ولا يمكن بأي حال من الأحوال أن تكون هذه الحسابات ذات رصيد عدين.
* **[S2]** REG-91-02, article 3 — statut calculé par le système : UNKNOWN
  > يستثنى من مجال تطبيق هذا النظام الأشخاص الطبيعيون والمعنويون ذوو جنسية بلد غير معترف به من طرف الجزائر. - المفتوحة باسم الأشخاص المشار اليهم في المادة الأولى أعلاه
* **[S3]** REG-91-02, article 1 — statut calculé par le système : UNKNOWN
  > يسمح للاشخاص المعنويين أو بفتح حساب بالعملة الصعبة لدى أي بنك جزائري وبأية عملة صعبة يختارونهاء وتشغيل هذا الحساب.
* **[S4]** REG-91-02, article 2 — statut calculé par le système : UNKNOWN
  > يفهم من العملة الصعبة كل due‏ أجنبية قابلة للتحويل بكل حرية ومستعملة عادة في المعاملات التجارية والمالية الدولية. (Ms‏ يقوم بنك الجزائر بتسعيرها

### Phase 4 (sortie `human_bench_dev_phase4.json`)

* Réponse : « Non, les comptes en devise ne peuvent pas être ouverts au nom des personnes mentionnées et avoir un solde en ville (en crédit). Cela est précisé dans l'Instruction n° 06-2021 du 29 juin 2021, qui indique que les comptes en devise pour les commerçants et les personnes exerçant une activité non commerciale ne peuvent pas enregistrer de solde en crédit [S4]. »
* Passages cités : INS-06-21.ar::article-3 ; rang du passage attendu dans la recherche : 1
* Notes du système : Correspondance partielle : vérifiez que ces passages répondent bien à votre question. | [S4] Statut de vigueur non déterminé (aucune relation ni période dans le corpus) : ne pas présenter comme applicable [règle U-ISOLE, confiance LOW].
* Notation automatique : réponse correcte = False ; refus à tort = False ; hallucination = True ; erreur temporelle critique = False ; statut correct = None
* Passages donnés au modèle :
* **[S1]** REG-09-01, article 4 — statut calculé par le système : UNKNOWN
  > يجب .أن تكون الحسابات بالعملة الصعبة المفتوحة بساسم ا لأشخاض المذكورين فى المدة الأولى أعلاه. في وهسعيسة دائئة Mai‏ ولا يمكن بأي حال من الأحوال أن تكون هذه الحسابات ذات رصيد عدين.
* **[S2]** REG-91-02, article 3 — statut calculé par le système : UNKNOWN
  > يستثنى من مجال تطبيق هذا النظام الأشخاص الطبيعيون والمعنويون ذوو جنسية بلد غير معترف به من طرف الجزائر. - المفتوحة باسم الأشخاص المشار اليهم في المادة الأولى أعلاه
* **[S3]** REG-91-02, article 1 — statut calculé par le système : UNKNOWN
  > يسمح للاشخاص المعنويين أو بفتح حساب بالعملة الصعبة لدى أي بنك جزائري وبأية عملة صعبة يختارونهاء وتشغيل هذا الحساب.
* **[S4]** **(citée)** INS-06-21, article 3 — statut calculé par le système : UNKNOWN
  > :ال يسمح لحساب العملة الصعبة للتاجر وحساب العملة الصعبة لصاحب المهنة غير التجارية أن يسجل أرصدة مدينة.

### Observations techniques (IA, non humaines ; aucune correction appliquée)

* Le passage attendu (REG-09-01, article 4) est classé **premier** dans les deux phases et fait partie du contexte. Son texte arabe est abîmé par l'OCR (« رصيد عدين » pour « رصيد مدين », mots parasites) ; le texte français officiel dit que ces comptes « ne peuvent en aucun cas présenter un solde débiteur ».
* En phase 3 le modèle a refusé. En phase 4, les articles arabes de l'instruction INS-06-21 sont détectés (1 → 15 articles) : son article 3 (« compte devise commerçant / professionnel non commerçant : pas de soldes débiteurs ») entre dans le contexte (S4) et c'est lui que le modèle cite. Cette instruction vise une **autre catégorie de comptes** que REG-09-01 ; la réponse écrit « solde en crédit » alors que le passage parle de « soldes débiteurs » (أرصدة مدينة).
* La question emploie « الأشخاص المذكورين » (« les personnes mentionnées ») sans antécédent : c'est peut-être une question ambiguë (à apprécier par le juriste).

### Questions au juriste (H120)

1. La question est-elle juridiquement valide (et bien posée) ? 
2. La source retrouvée par le système (INS-06-21 art. 3) est-elle pertinente pour cette question ? La source attendue (REG-09-01 art. 4) l'est-elle ?
3. La réponse produite est-elle juridiquement correcte ? Contient-elle une hallucination ?
4. Le système aurait-il dû refuser ?

## H129 — taux « actuel » des réserves obligatoires (question en arabe)

**Question** (J_fr_ar, difficulté moyen, langue ar) : ما هو معدل الاحتياطيات الإجبارية المعمول به حاليا؟

**Attendu (rédigé par une IA, non validé)** : INS-01-26 article 2 ; date de référence : actuel ; statut attendu : ACTIVE
* Réponse attendue : 1% من وعاء الاحتياطيات (التعليمة رقم 01-2026).
* Passage attendu (texte français officiel) : « Le taux des réserves obligatoires est fixé à 1% de l'assiette » — L’article 3 de l'instruction n° 02-2004 du 13 mai 2004 relative au régime des réserves obligatoires est modifié et rédigé comme suit :
« Article 3 : Le taux des réserves obligatoires est fixé à 1% de l'assiette des réserves définie dans l'article 2 c
* Versions à ne PAS présenter comme actuelles (liste du benchmark, par article) : INS-02-04 art. 3, INS-13-07 art. 2, INS-04-10 art. 2, INS-01-12 art. 2, INS-02-13 art. 2, INS-03-16 art. 2, INS-04-17 art. 2, INS-01-18 art. 2, INS-03-18 art. 2, INS-01-19 art. 2, INS-02-19 art. 2, INS-02-20 art. 2, INS-06-20 art. 2, INS-09-20 art. 2, INS-02-21 art. 2, INS-02-23 art. 2, INS-09-25 art. 2

**Problème actuel** : *valeur périmée* → *présentée comme actuelle* → *la notation automatique ne la considère pas comme erreur critique*.

### Phase 3 (sortie gelée `human_bench_dev_final2.json`)

* Réponse : « معدل الاحتياطيات الإجبارية المعمول به حالياً هو 2.90 من وعاء الاحتياطيات الإجبارية، وفقاً للتعديل المذكور في التعليمة رقم 02-2021 المؤرخة في 7 فيفري 2021 [S2]. »
* Passages cités : INS-02-21.ar::article-2 ; rang du passage attendu dans la recherche : None
* Notes du système : Correspondance partielle : vérifiez que ces passages répondent bien à votre question. | [S2] Remplacé d'après Instruction n° 02-2023 du 13 avril 2023, article 2 : version antérieure [règle R-ART-REMPL, confiance MEDIUM].
* Notation automatique : réponse correcte = False ; refus à tort = False ; hallucination = False ; erreur temporelle critique = True ; statut correct = False
* Passages donnés au modèle :
* **[S1]** INS-02-20, article 2 — statut calculé par le système : REPLACED
  > نُعدّل المادة 3 من التعليمة رقم 2004-02 المؤرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحوّر على النحو التالي : » المادة 3 : يُحدّد معدل الاحتياطيات الإجبارية ب 08 90 من وعاء الاحتياطيات الإجبارية المنتصوص علية في المادة 2 أعلده».
* **[S2]** **(citée)** INS-02-21, article 2 — statut calculé par le système : REPLACED
  > تُعذل المادة 3 من التعليمة رقم 2004-02 المؤّرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحرّر على النحو التالي: « المادة 3 : das‏ معدل الاحتياطيات الإجبارية ب 2 90 من وعاء الاحتياطيات الإجبارية المنصوص عليه في المادة 2 أعلاه ».
* **[S3]** INS-01-19, article 2 — statut calculé par le système : REPLACED
  > تعدّل المادة 3 من التعليمة رقم 2004-02 المؤرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحرّر على النحو A‏ « المادة 3 : يُحدّد معدل الاحتياطيات الإجبارية ب 9612 من وعاء الاحتياطيات الإجبارية المنصوص عليه في المادة 2 أعلاه».
* **[S4]** INS-02-19, article 2 — statut calculé par le système : REPLACED
  > تُعدّل المادة 3 من التعليمة رقم 2004-02 المؤرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحرّر على النحو التالي : بر المادة 3 : das‏ معدل الاحتياطيات الإجبارية ب 9010 من وعاء الاحتياطيات الإجبارية المنتصوص عليه في المادة 2 أعلاة». المادةٌ 3 : يسري مفعول هذه التعليمة ابتداء من تاريخ 15 ديسمبر 2019

### Phase 4 (sortie `human_bench_dev_phase4.json`)

* Réponse : « معدل الاحتياطيات الإجبارية المعمول به حالياً هو 3%، وفقاً للتعليمية رقم 02-2023 المؤرخة في 13 أبريل 2023، التي تُعدّل المادة 3 من التعليمة رقم 02-2004 المؤرخة في 13 مايو 2004، وتمت إدراجها في النص بوضوح في المادة 3 من هذه التعليمية [S3]. هذا النص يُعتبر نسخة نشطة (ACTIVE) حسب مُعطى الوضع القانوني. »
* Passages cités : INS-02-23.ar::article-3 ; rang du passage attendu dans la recherche : None
* Notes du système : Correspondance partielle : vérifiez que ces passages répondent bien à votre question.
* Notation automatique : réponse correcte = False ; refus à tort = False ; hallucination = False ; erreur temporelle critique = False ; statut correct = True
* Passages donnés au modèle :
* **[S1]** INS-02-20, article 2 — statut calculé par le système : REPLACED
  > نُعدّل المادة 3 من التعليمة رقم 2004-02 المؤرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحوّر على النحو التالي : » المادة 3 : يُحدّد معدل الاحتياطيات الإجبارية ب 08 90 من وعاء الاحتياطيات الإجبارية المنتصوص علية في المادة 2 أعلده».
* **[S2]** INS-01-19, article 2 — statut calculé par le système : REPLACED
  > تعدّل المادة 3 من التعليمة رقم 2004-02 المؤرخة في 13 ماي 2004 المتعلقة بنظام الاحتياطيات الإجبارية وتحرّر على النحو A‏ « المادة 3 : يُحدّد معدل الاحتياطيات الإجبارية ب 9612 من وعاء الاحتياطيات الإجبارية المنصوص عليه في المادة 2 أعلاه».
* **[S3]** **(citée)** INS-02-23, article 3 — statut calculé par le système : ACTIVE
  > يُحدّد معدل االحتياطيات اإلجبارية بـ 3 من وعاء االحتياطيات% اإل جبارية المنصوص عليه في المادة2 أعاله.»
* **[S4]** INS-02-13, article 2 — statut calculé par le système : REPLACED
  > Dax‏ المادة 3 من التعليمة رقم 2004-2 المؤرخة في 13 ماي 2004 والمتعلقة بنظام الاحتياطيات الإجبارية وتحرر على النحو التالي : « المادة 3 : يُحدّد معدل الاحتياطيات الإجبارية ب 9012 من وعاء الاحتياطيات الإجبارية المنصوص عليها في المادة 2 أعلاه».

### Observations techniques (IA, non humaines ; aucune correction appliquée)

* Phase 3 : le modèle cite INS-02-21 art. 2 (valeur arabe abîmée « 2.90 ») ; la règle automatique signale une erreur temporelle critique (le texte cité est dans la liste des versions interdites).
* Phase 4 : le modèle cite **INS-02-23, « article 3 »**. Ce chunk arabe est le texte **cité** par l'instruction (« L'article 3 … est modifié et rédigé comme suit : « Article 3 : … 3 % … » ») : la détection d'en-têtes d'articles arabes, corrigée en phase 4, a découpé l'article 2 d'INS-02-23 au niveau de l'article cité et l'a étiqueté « article 3 ». Le statut juridique calculé pour « INS-02-23 art. 3 » est **ACTIVE**, car aucun texte ne modifie l'article 3 *de INS-02-23* ; le texte visé (article 3 d'INS-02-04) a pourtant été remplacé depuis (INS-09-25 : 2 %, puis INS-01-26 : 1 %). Le modèle recopie « ACTIVE ». L'instruction actuelle INS-01-26 n'est pas retrouvée en arabe (sa valeur est abîmée par l'OCR : « د 1 % »).
* La notation automatique ne signale pas d'erreur temporelle critique en phase 4 (le texte cité est l'article 3 alors que la liste des versions interdites désigne l'article 2) et juge même le **statut correct** (ACTIVE calculé = ACTIVE attendu) : **divergence entre la notation automatique et l'analyse qualitative**. La règle de notation n'est pas modifiée.
* Indicateur approximatif de l'ampleur (analyse, non corrigé) : environ 20 chunks arabes (15 documents) suivent immédiatement un chunk qui se termine par une ouverture de citation « ; 14 existaient déjà en phase 3.

### Questions au juriste (H129)

1. La question est-elle juridiquement valide ? La valeur attendue (1 %, INS-01-26) est-elle la bonne valeur « actuelle » ?
2. La réponse (3 %, présentée comme valeur actuelle et « ACTIVE ») est-elle une **erreur juridique critique**, ou une autre catégorie (précisez) ?
3. La version temporelle est-elle correcte ? La citation est-elle correcte (article cité) ?
4. Le juriste confirme-t-il l'écart entre la notation automatique (pas d'erreur critique, statut correct) et son analyse ?

## Rappel : autres cas déjà signalés (à qualifier aussi)

| Cas | Pourquoi | Dans l'échantillon de 60 ? |
|---|---|---|
| H130 | taux directeur en arabe : « 902.75 % » au lieu de 2,75 % (OCR : « % » lu « 90 ») ; la réponse porte maintenant l'alerte `OCR_UNCERTAIN` | oui |
| H041 | la réponse recopie une date de référence de la consigne interne (« métadonnée interne » ?) : à qualifier par le juriste, non tranché | oui |
| H055 | la réponse recopie une date de référence de la consigne interne (« métadonnée interne » ?) : à qualifier par le juriste, non tranché | non |
| H039 | la réponse recopie une date de référence de la consigne interne (« métadonnée interne » ?) : à qualifier par le juriste, non tranché | non |
| H053 | la réponse recopie une date de référence de la consigne interne (« métadonnée interne » ?) : à qualifier par le juriste, non tranché | oui |

