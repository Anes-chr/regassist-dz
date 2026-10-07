"""Construit gold_v4.jsonl : jeu VIERGE de la phase 2 — écrit APRÈS le réglage des seuils et AVANT l'implémentation de la résolution de versions.
Contient la chaîne réelle des taux de réserves obligatoires (instruction 02-2004, 17 valeurs de 2004 à 2026) et de nouveaux faits.
Chaque réponse attendue est vérifiée mécaniquement sur l'instantané figé. Relecture : assistant IA, pas un juriste humain."""
import json
import os
import re
from pathlib import Path

SNAP = Path(os.environ.get("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06"))
HERE = Path(__file__).resolve().parent
chunks, allc = {}, []
for l in open(SNAP / "chunks_fr.jsonl", encoding="utf-8"):
    c = json.loads(l)
    allc.append(c)
    chunks.setdefault((c["work_id"], c.get("article")), []).append(c)
    chunks.setdefault((c["work_id"], None), []).append(c)


def norm(s):
    return " ".join(s.replace("’", "'").lower().split())


V = "Claude (relecture automatisée contre le texte extrait) — pas un juriste humain"
OUT = []
RES_CHAIN = ["INS-02-04", "INS-13-07", "INS-04-10-20101215", "INS-01-12-20120429", "INS-02-13-20130423", "INS-03-16-20160425", "INS-04-17-20170731",
             "INS-01-18-20180110", "INS-03-18-20180531", "INS-01-19-20190214", "INS-02-19-20191205", "INS-02-20-20200310", "INS-06-20-20200429",
             "INS-09-20-20200914", "INS-02-21-20210207", "INS-02-23-20230413", "INS-09-25-20250910", "INS-01-26-20260107"]


def add(cat, q, expected=None, facts=None, **kw):
    expected = expected or []
    for w, a in expected:
        assert chunks.get((w, a)), f"passage attendu introuvable : {w} art. {a}"
    for f in facts or []:
        assert any(norm(f) in norm(c["text"]) for w, a in expected for c in chunks[(w, a)]), f"fait clé absent : {f!r}"
    OUT.append({"id": f"W{len(OUT) + 1:03d}", "split": "v4", "category": cat, "question": q,
                "expected": [{"work_id": w, "article": a} for w, a in expected], "key_facts": facts or [], "validated_by": V, "synthetic": False, **kw})


def stale(expected_works):
    return [w for w in RES_CHAIN if w not in expected_works]


# ---- Directes (nouveaux faits)
add("direct_delai", "Dans quel délai doit se tenir la réunion du Comité en cas de défaut de règlement d'une banque ?", [("INS-03-08", "5")], ["trois(3) heures"])
add("direct_delai", "En combien de temps s'exécutent les appels d'offres rapides pour les reprises de liquidité ?", [("INS-01-13", "4")], ["deux (2) heures"])
add("direct_delai", "Dans quel délai une banque adjudicataire doit-elle créditer le compte de règlement de la Banque d'Algérie après l'ouverture de la journée d'échange ?", [("INS-06-16", "19")], ["soixante (60) minutes"])
add("direct_obligation", "Que doivent faire les établissements déclarants au sujet du spécimen de signature de leurs personnes habilitées ?", [("INS-01-11-20110309", "39")], ["trente (30) jours"])
add("direct_montant", "Pendant combien de mois au maximum les effets créés en représentation de crédits à moyen terme sont-ils réescomptables ?", [("REG-00-01", "9")], ["six (06) mois"])
add("reference", "Quel est le montant maximal du droit de change pour soins à l'étranger fixé par l'instruction n° 10-96 ?", [("INS-10-96", "3")], ["120.000"])
# ---- État actuel / historique sur une chaîne de modifications (17 valeurs) : la bonne version, pas la plus proche
add("etat_actuel", "Quel est le taux actuel des réserves obligatoires ?", [("INS-01-26-20260107", "2")], ["1%"], stale_top1=stale(["INS-01-26-20260107"]))
add("historique", "Quel était le taux des réserves obligatoires en 2013 ?", [("INS-02-13-20130423", "2")], ["12 %"], as_of=2013, stale_top1=stale(["INS-02-13-20130423"]))
add("historique", "Quel était le taux des réserves obligatoires en 2017 ?", [("INS-04-17-20170731", "2")], ["4%"], as_of=2017, stale_top1=stale(["INS-04-17-20170731"]))
add("historique", "Quel était le taux des réserves obligatoires au 1er mars 2018 ?", [("INS-01-18-20180110", "2")], ["8 %"], as_of=2018, stale_top1=stale(["INS-01-18-20180110"]))
add("historique", "Quel était le taux des réserves obligatoires en juin 2019 ?", [("INS-01-19-20190214", "2")], ["12 %"], as_of=2019, stale_top1=stale(["INS-01-19-20190214"]))
add("historique", "Quel était le taux des réserves obligatoires en 2005 ?", [("INS-02-04", "3")], ["6,5%"], as_of=2005, stale_top1=stale(["INS-02-04"]))
# ---- Plusieurs modifications : TOUS les textes attendus
add("multi_textes", "Quels taux de réserves obligatoires ont été fixés au cours de l'année 2020 ?",
    [("INS-02-20-20200310", "2"), ("INS-06-20-20200429", "2"), ("INS-09-20-20200914", "2")], ["08%", "6%", "3%"], mode="all")
add("modification", "Quelles instructions ont modifié le taux des réserves obligatoires en 2018 ?",
    [("INS-01-18-20180110", "2"), ("INS-03-18-20180531", "2")], ["8 %", "10 %"], mode="all")
add("etat_actuel", "Quel est le taux de réescompte actuellement applicable ?", [("INS-03-17", None)], ["3,75"], stale_top1=["INS-05-16", "INS-01-98"])
# ---- Hors corpus
for q, pat in [("Quelle est la durée du service national en Algérie ?", r"service national"),
               ("Quel est le montant de la pension de retraite minimale ?", r"pension de retraite"),
               ("Comment contester une amende de stationnement ?", r"amende de stationnement")]:
    assert not [c for c in allc if re.search(pat, c["text"], re.I)], f"le corpus contient « {pat} »"
    OUT.append({"id": f"W{len(OUT) + 1:03d}", "split": "v4", "category": "hors_corpus", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---- Hors sujet
for q in ["Quelle est la hauteur de la tour Eiffel ?", "Traduis « bonjour » en anglais.", "Qui a peint la Joconde ?"]:
    OUT.append({"id": f"W{len(OUT) + 1:03d}", "split": "v4", "category": "hors_sujet", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---- Ambigus
for q in ["Quelle est la durée ?", "Quelles sont les conditions ?"]:
    OUT.append({"id": f"W{len(OUT) + 1:03d}", "split": "v4", "category": "ambigu", "question": q, "expect_clarify": True, "validated_by": V, "synthetic": False})
# ---- Arabe (question arabe -> même acte)
for q, w in [("ما هي نسبة الاحتياطي الإلزامي المطبقة حاليا؟", "INS-01-26-20260107"),
             ("ما هي مدة تنفيذ طلبات العروض السريعة لاسترجاع السيولة؟", "INS-01-13"),
             ("ما هو الحد الأقصى لمبلغ حق الصرف للعلاج في الخارج حسب التعليمة رقم 10-96؟", "INS-10-96")]:
    OUT.append({"id": f"W{len(OUT) + 1:03d}", "split": "v4", "category": "arabe", "question": q, "expected": [{"work_id": w, "article": None}],
                "any_language": True, "validated_by": V, "synthetic": False})

with open(HERE / "gold_v4.jsonl", "w", encoding="utf-8") as f:
    for r in OUT:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print(len(OUT), "questions", dict(Counter(r["category"] for r in OUT)))
