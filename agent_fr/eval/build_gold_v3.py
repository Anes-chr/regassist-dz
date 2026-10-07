"""Construit gold_v3.jsonl : jeu de test PHASE 2 (retrieval juridique), écrit AVANT d'évaluer la nouvelle recherche.
Catégories : direct (définition/montant/délai/obligation/interdiction/procédure), multi-textes, historique, état actuel, modification,
hors corpus, hors sujet, ambigu, arabe→texte. Chaque réponse attendue est vérifiée mécaniquement sur l'INSTANTANÉ figé du corpus.
Relecture : assistant IA (Claude), pas un juriste humain."""
import json
import os
import re
from pathlib import Path

SNAP = Path(os.environ.get("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06"))
HERE = Path(__file__).resolve().parent
chunks = {}
allc = []
for l in open(SNAP / "chunks_fr.jsonl", encoding="utf-8"):
    c = json.loads(l)
    allc.append(c)
    chunks.setdefault((c["work_id"], c.get("article")), []).append(c)
    chunks.setdefault((c["work_id"], None), []).append(c)


def norm(s):
    return " ".join(s.replace("’", "'").lower().split())


V = "Claude (relecture automatisée contre le texte extrait) — pas un juriste humain"
OUT = []


def add(cat, q, expected=None, facts=None, **kw):
    expected = expected or []
    for w, a in expected:
        cs = chunks.get((w, a))
        assert cs, f"passage attendu introuvable : {w} art. {a}"
    for f in facts or []:
        assert any(norm(f) in norm(c["text"]) for w, a in expected for c in chunks[(w, a)]), f"fait clé absent : {f!r}"
    OUT.append({"id": f"V{len(OUT) + 1:03d}", "split": "v3", "category": cat, "question": q,
                "expected": [{"work_id": w, "article": a} for w, a in expected], "key_facts": facts or [],
                "validated_by": V, "synthetic": False, **kw})


# ---- Directes
add("direct_definition", "Qu'appelle-t-on coût d'acquisition dans un contrat de Mourabaha ?", [("INS-03-20", "4")], ["prix d'achat du bien acquis"])
add("direct_definition", "Que désigne la partie imprimée d'un effet de commerce ?", [("INS-01-20", "5")], ["caractères d'imprimerie"])
add("direct_montant", "À quel niveau a été ramené le seuil minimum du coefficient de liquidité par les mesures exceptionnelles de 2020 ?", [("INS-05-20", "2")], ["60%"])
add("direct_delai", "Dans quel délai la Banque d'Algérie désigne-t-elle une banque à une personne dont l'ouverture de compte a été refusée ?", [("INS-03-12", "4")], ["cinq (5) jours ouvrés"])
add("direct_delai", "Quel délai a une banque pour compléter un dossier de crédit jugé incomplet par la Banque d'Algérie ?", [("INS-02-16", "26")], ["quinze (15) jours"])
add("direct_obligation", "Que doit faire une banque qui refuse d'ouvrir un compte de dépôt à un demandeur ?", [("INS-03-12", "5")], ["est tenue d’informer le demandeur"])
add("direct_interdiction", "Peut-on prévoir une clause pénale pour retard de livraison dans un contrat Salam ?", [("INS-03-20", "40")], ["interdit de stipuler de clauses pénales"])
add("direct_interdiction", "La facturation en devises de biens et services sur le territoire national est-elle permise ?", [("INS-02-94", "2")], ["est interdite"])
add("direct_procedure", "À qui les banques adressent-elles les dossiers de crédit des entreprises publiques pour le contrôle a posteriori ?", [("INS-02-16", "24")], ["Direction du Refinancement"])
# ---- Multi-textes (TOUS les passages attendus doivent être retrouvés)
add("multi_textes", "Quels textes ont successivement fixé le plafond d'indemnisation des déposants ?",
    [("REG-97-04", "9"), ("REG-04-03", "8"), ("REG-18-01-20180430", "5"), ("REG-20-03", "10")], ["600.000", "deux millions"], mode="all")
add("multi_textes", "Quel était le montant du droit de change pour soins à l'étranger en 1995 puis en 1996 ?",
    [("INS-47-95", "3"), ("INS-10-96", "3")], ["100.000", "120.000"], mode="all")
add("multi_textes", "Quel règlement fixe ce que les voyageurs peuvent exporter en devises, et quel texte récent l'a modifié ?",
    [("REG-16-02", "5"), ("REG-24-05-20241013", "2")], ["7500", "sept mille cinq cent"], mode="all")
# ---- Historiques (la version D'ÉPOQUE doit être en tête, pas la plus récente)
add("historique", "Quel était le plafond d'indemnisation des déposants en 1998 ?", [("REG-97-04", "9")], ["600.000"], as_of=1998, stale_top1=["REG-20-03", "REG-18-01-20180430"])
add("historique", "Quel était le plafond d'indemnisation par déposant avant 2018 ?", [("REG-04-03", "8")], ["600.000"], as_of=2017, stale_top1=["REG-20-03", "REG-18-01-20180430"])
add("historique", "Quel était le taux de réescompte au 1er septembre 2016 ?", [("INS-05-16", None)], ["3,5"], as_of=2016, stale_top1=["INS-03-17"])
add("historique", "Quel était le taux de réescompte en avril 1997 ?", [("INS-04-97", None)], ["12,5"], as_of=1997, stale_top1=["INS-03-17", "INS-05-16"])
add("historique", "Quel était le montant du droit de change pour soins à l'étranger en 1995 ?", [("INS-47-95", "3")], ["100.000"], as_of=1995, stale_top1=["INS-10-96"])
# ---- État actuel (sans date : la valeur la plus récente du corpus, pas l'ancienne)
add("etat_actuel", "Quel est le plafond actuel d'indemnisation des déposants ?", [("REG-20-03", "10")], ["deux millions"], stale_top1=["REG-04-03", "REG-97-04"])
add("etat_actuel", "Quel montant maximal un voyageur peut-il actuellement sortir d'Algérie ?", [("REG-24-05-20241013", "2")], ["sept mille cinq cent"], stale_top1=["REG-16-02"])
add("etat_actuel", "Quelle est actuellement l'indemnité journalière de mission à l'étranger d'un cadre dirigeant ?", [("INS-02-24", "6")], ["32000"], stale_top1=["INS-01-03", "INS-22-92"])
# ---- Modifications / abrogations
add("modification", "Quel texte a modifié l'article 5 du règlement n° 16-02 ?", [("REG-24-05-20241013", "2")], ["16-02"])
add("modification", "Quel règlement a abrogé le règlement n° 97-04 ?", [("REG-04-03", "20")], ["97-04"])
add("modification", "Quel règlement a modifié le plafond d'indemnisation fixé par le règlement n° 04-03 ?", [("REG-18-01-20180430", "5")], ["deux millions"])
add("modification", "Quelle instruction a ramené à 1 % le taux des réserves obligatoires ?", [("INS-01-26-20260107", "2")], ["1%"])
# ---- Hors corpus (légal mais absent) : refus attendu
for q, pat in [("Quelle est la durée maximale de la garde à vue en Algérie ?", r"garde à vue"),
               ("Quelle est la durée légale du congé de maternité en Algérie ?", r"maternité"),
               ("Quel est le salaire national minimum garanti en Algérie ?", r"SNMG|salaire national minimum"),
               ("Que prévoit le code de la route pour la vitesse maximale en ville ?", r"code de la route|vitesse maximale")]:
    assert not [c for c in allc if re.search(pat, c["text"], re.I)], f"le corpus contient « {pat} » : question non valide"
    OUT.append({"id": f"V{len(OUT) + 1:03d}", "split": "v3", "category": "hors_corpus", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---- Hors sujet : refus attendu (certains reprennent des mots du corpus : pièges)
for q in ["Quelle est la capitale du Japon ?", "Qui a remporté la Coupe du monde de football en 2018 ?", "Donne-moi une recette de tajine aux olives.",
          "Comment installer Python sur Windows ?"]:
    OUT.append({"id": f"V{len(OUT) + 1:03d}", "split": "v3", "category": "hors_sujet", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---- Ambigus : demander une précision (ni refus sec, ni réponse inventée)
for q in ["Quel est le taux ?", "Quel est le plafond ?", "Que dit l'article 5 ?"]:
    OUT.append({"id": f"V{len(OUT) + 1:03d}", "split": "v3", "category": "ambigu", "question": q, "expect_clarify": True, "validated_by": V, "synthetic": False})
# ---- Arabe : question arabe -> texte du même acte (français ou arabe, même work_id)
for q, w, a in [("ما هو سقف التعويض لكل مودع في نظام ضمان الودائع المصرفية؟", "REG-20-03", "10"),
                ("ما هو الحد الأدنى لمعامل الملاءة الذي يجب على البنوك احترامه؟", "REG-14-01", "2"),
                ("كيف تُعرَّف المخاطر الكبرى في النظام المتعلق بالمخاطر الكبرى والمساهمات؟", "REG-14-02", "2"),
                ("من له صلاحية تحديد سعر الفائدة المفرط؟", "REG-09-03", "5"),
                ("هل القرض داخل اليوم الذي يمنحه بنك الجزائر مجاني؟", "REG-05-04", "31"),
                ("ما هي المدة الممنوحة للمؤسسات للامتثال لأحكام النظام رقم 25-07؟", "REG-25-07", "7")]:
    assert chunks.get((w, a))
    OUT.append({"id": f"V{len(OUT) + 1:03d}", "split": "v3", "category": "arabe", "question": q, "expected": [{"work_id": w, "article": None}],
                "any_language": True, "validated_by": V, "synthetic": False})

with open(HERE / "gold_v3.jsonl", "w", encoding="utf-8") as f:
    for r in OUT:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print(len(OUT), "questions", dict(Counter(r["category"] for r in OUT)))
