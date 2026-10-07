"""Construit gold_v5.jsonl : jeu VIERGE de validation finale de la phase 2.

Règles de construction (fixées AVANT toute mesure sur ce jeu) :
  - passages attendus tirés de textes qui n'apparaissent comme réponse attendue ni dans gold_v2, ni dans gold_v3, ni dans gold_v4 ;
  - chaque passage attendu et chaque fait clé est vérifié mécaniquement sur l'instantané figé (assertions) ;
  - le jeu est lancé UNE SEULE FOIS sur chaque pipeline ; aucun réglage n'est fait ensuite à partir de ses résultats sans le déclarer
    (si on le consulte pour corriger quelque chose, il cesse d'être vierge et le rapport l'indique) ;
  - l'empreinte SHA-256 du fichier produit est écrite dans gold_v5.sha256 pour prouver qu'il n'a pas été modifié après les mesures.
Relecture : assistant IA (relecture automatisée contre le texte extrait), pas un juriste humain."""
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

SNAP = Path(os.environ.get("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06"))
HERE = Path(__file__).resolve().parent
chunks, allc = {}, []
for l in open(SNAP / "chunks_fr.jsonl", encoding="utf-8"):
    c = json.loads(l)
    allc.append(c)
    chunks.setdefault((c["work_id"], c.get("article")), []).append(c)
    chunks.setdefault((c["work_id"], None), []).append(c)
ar_works = {json.loads(l)["work_id"] for l in open(SNAP / "chunks_ar.jsonl", encoding="utf-8")}
fr_works = {c["work_id"] for c in allc}


def squash(s):
    return re.sub(r"\s+", "", str(s).replace("’", "'").lower().replace("\u00a0", " "))


V = "Claude (relecture automatisée contre le texte extrait) — pas un juriste humain"
OUT = []

RESC = ["INS-04-97", "INS-05-97", "INS-09-97", "INS-01-98", "INS-05-99", "INS-01-00", "INS-08-00", "INS-01-02", "INS-02-03", "INS-01-04", "INS-05-16", "INS-03-17"]
PRIME = ["INS-09-00", "INS-05-02", "INS-03-03", "INS-04-04", "INS-05-05", "INS-04-06", "INS-07-07", "INS-05-08", "INS-04-09", "INS-03-10", "INS-06-11",
         "INS-02-12", "INS-03-13", "INS-02-14", "INS-01-16", "INS-10-16", "INS-02-18", "INS-04-18", "INS-03-19", "INS-13-20", "INS-01-23", "INS-01-24", "INS-07-25"]
DC = ["INS-08-97", "INS-05-25", "INS-07-26"]


def add(cat, q, expected=None, facts=None, **kw):
    expected = expected or []
    for w, a in expected:
        assert chunks.get((w, a)), f"passage attendu introuvable : {w} art. {a}"
    for f in facts or []:
        assert any(squash(f) in squash(c["text"]) for w, a in expected for c in chunks[(w, a)]), f"fait clé absent : {f!r} dans {expected}"
    OUT.append({"id": f"X{len(OUT) + 1:03d}", "split": "v5", "category": cat, "question": q,
                "expected": [{"work_id": w, "article": a} for w, a in expected], "key_facts": facts or [], "validated_by": V, "synthetic": False, **kw})


def stale(chain, keep):
    return [w for w in chain if w not in keep]


# ---------------------------------------------------------------- Directes : définition / obligation / interdiction / procédure / délai
add("direct_definition", "Au sens du règlement sur l'apport de liquidité d'urgence, quand une banque est-elle jugée viable ?", [("REG-25-04", "2")], ["rentabilité suffisante"])
add("direct_definition", "Quel est l'effet de la subrogation en matière d'affacturage ?", [("REG-26-03", "8")], ["de plein droit", "factor"])
add("direct_definition", "Quelles effigies figurent sur les revers des pièces de 10 DA argent frappées en 1994 ?", [("REG-94-16", "2")], ["JUGURTHA", "BENBADIS", "BOUMEDIENE"])
add("direct_definition", "Sur quelles exigibilités les réserves obligatoires des banques sont-elles constituées selon le règlement 2004-02 ?", [("REG-04-02", "4")], ["exigibilités collectées"])
add("direct_obligation", "Quelle obligation les participants aux systèmes de paiement ont-ils à l'égard des informations qui transitent par ces systèmes ?", [("REG-05-07", "10")], ["confidentialité", "intégrité"])
add("direct_obligation", "Dans quels documents le taux d'intérêt effectif global doit-il être mentionné ?", [("INS-08-16", "11")], ["offre de crédit"])
add("direct_obligation", "Comment les produits importés pour la revente en l'état par les concessionnaires et grossistes peuvent-ils être réglés ?", [("REG-90-04", "5")], ["comptes devises"])
add("direct_obligation", "Un voyageur qui quitte l'Algérie peut-il exporter des billets de banque étrangers, et jusqu'à quel montant ?", [("REG-95-07-19951223", "20")], ["montant déclaré à l'entrée"])
add("direct_interdiction", "Les comptes devises « commerçants » peuvent-ils être débiteurs ou recevoir des avances en devises ?", [("INS-29-94", "13")], ["en aucun cas être débiteurs"])
add("direct_procedure", "Que doit faire la banque domiciliataire d'un budget lorsque l'examen du justificatif révèle une irrégularité grave ?", [("INS-04-02", "16")], ["Direction Générale des Changes", "mesures conservatoires"])
add("direct_procedure", "Comment une banque qui n'est pas Spécialiste en Valeurs du Trésor peut-elle participer à la facilité de prêt marginal ?", [("INS-07-16-20160901", "8")], ["banque correspondant"])
add("direct_procedure", "Qui effectue l'inspection sur le site d'implantation d'un guichet de banque, et à qui le rapport est-il adressé ?", [("INS-01-99", "8")], ["Gouverneur"])
add("reference", "Selon le règlement n°92-01, qui est tenu d'adhérer à la Centrale des Risques ?", [("REG-92-01", "3")], ["Organismes de Crédit"])
# ---------------------------------------------------------------- État actuel (textes successivement abrogés / séries annuelles sans relation)
add("etat_actuel", "Quel est le montant annuel maximum du droit de change pour voyage à l'étranger actuellement en vigueur ?", [("INS-07-26", "2")], ["750,00 EUR"], stale_top1=stale(DC, ["INS-07-26"]))
add("etat_actuel", "Quelle durée de séjour minimale donne droit au montant maximum du droit de change pour voyage à l'étranger ?", [("INS-07-26", "3")], ["sept (7) jours"], stale_top1=["INS-05-25", "INS-08-97"])
add("etat_actuel", "Quel est le taux actuel de la prime due au fonds de garantie des dépôts bancaires ?", [("INS-07-25", "2")], ["0,1%"], stale_top1=stale(PRIME, ["INS-07-25"]))
# ---------------------------------------------------------------- Historique : la version applicable à la date demandée
add("historique", "Quel était le montant annuel du droit de change pour voyage à l'étranger en 1998 ?", [("INS-08-97", "2")], ["15.000"], as_of=1998, stale_top1=stale(DC, ["INS-08-97"]))
add("historique", "Quel était le montant annuel maximum du droit de change pour voyage à l'étranger en septembre 2025 ?", [("INS-05-25", "2")], ["750,00 EUR"], as_of=2025, stale_top1=stale(DC, ["INS-05-25"]))
add("historique", "Quel était le taux de la prime due au fonds de garantie des dépôts bancaires en 2003 ?", [("INS-03-03", "2")], ["0,35%"], as_of=2003, stale_top1=stale(PRIME, ["INS-03-03"]))
add("historique", "Quel était le taux de la prime due au fonds de garantie des dépôts bancaires en 2000 ?", [("INS-09-00", "2")], ["0,4%"], as_of=2000, stale_top1=stale(PRIME, ["INS-09-00"]))
add("historique", "Quel était le taux de la prime due au fonds de garantie des dépôts bancaires en 2024 ?", [("INS-01-24", "2")], ["0,15%"], as_of=2024, stale_top1=stale(PRIME, ["INS-01-24"]))
add("historique", "Quel était le taux de réescompte en juin 1997 ?", [("INS-05-97", None)], ["12 %"], as_of=1997, stale_top1=stale(RESC, ["INS-05-97"]))
add("historique", "Quel était le taux de réescompte au 1er décembre 1999 ?", [("INS-05-99", None)], ["8,5%"], as_of=1999, stale_top1=stale(RESC, ["INS-05-99"]))
add("historique", "Quel était le taux de réescompte en 2001 ?", [("INS-08-00", None)], ["6%"], as_of=2001, stale_top1=stale(RESC, ["INS-08-00"]))
add("historique", "Quel était le taux de réescompte en 2012 ?", [("INS-01-04", None)], ["4%"], as_of=2012, stale_top1=stale(RESC, ["INS-01-04"]))
add("direct_delai", "Jusqu'à quelle date les banques devaient-elles verser la prime au fonds de garantie des dépôts bancaires en 2012 ?", [("INS-02-12", "3")], ["15 décembre 2012"], as_of=2012, stale_top1=stale(PRIME, ["INS-02-12"]))
# ---------------------------------------------------------------- Plusieurs textes : TOUS les passages attendus
add("multi_textes", "Quelles instructions ont fixé le taux de réescompte au cours de l'année 1997 ?", [("INS-04-97", None), ("INS-05-97", None), ("INS-09-97", None)], ["12,5", "12 %", "11 %"], mode="all")
add("multi_textes", "Quelles instructions ont fixé le taux de la prime due au fonds de garantie des dépôts bancaires en 2016 ?", [("INS-01-16", "2"), ("INS-10-16", "2")], ["0,25 %"], mode="all")
# ---------------------------------------------------------------- Modification / remplacement (relations juridiques)
add("modification", "Quelles instructions ont modifié l'instruction n°22-92 du 10 juin 1992 ?", [("INS-13-95", None), ("INS-17-94", None), ("INS-39-95", None), ("INS-01-03", None)], mode="all")
add("modification", "Quel règlement a modifié et remplacé le règlement n°92-04 du 22 mars 1992 relatif au contrôle des changes ?", [("REG-95-07-19951223", None)])
add("modification", "Quelle instruction a modifié l'instruction n°71-92 du 24 novembre 1992 ?", [("INS-47-93", None)])
add("modification", "Quel règlement a remplacé le règlement n°92-01 portant organisation et fonctionnement de la Centrale des risques ?", [("REG-12-01", None)])
# ---------------------------------------------------------------- Hors corpus (absence vérifiée mécaniquement sur FR + AR)
for q, pat in [("Quelle est la durée du congé de maternité en Algérie ?", r"cong[ée] de maternit|maternit"),
               ("Quel est le montant du salaire national minimum garanti ?", r"SNMG|salaire (national )?minimum"),
               ("Quelles pièces faut-il fournir pour obtenir un permis de construire ?", r"permis de construire")]:
    assert not [c for c in allc if re.search(pat, c["text"], re.I)], f"le corpus contient « {pat} »"
    OUT.append({"id": f"X{len(OUT) + 1:03d}", "split": "v5", "category": "hors_corpus", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---------------------------------------------------------------- Hors sujet
for q in ["Combien de planètes compte le système solaire ?", "Écris-moi un poème sur la mer.", "Quel est le meilleur club de football d'Algérie ?"]:
    OUT.append({"id": f"X{len(OUT) + 1:03d}", "split": "v5", "category": "hors_sujet", "question": q, "expect_refuse": True, "validated_by": V, "synthetic": False})
# ---------------------------------------------------------------- Ambigus : le système doit demander une précision
for q in ["Quel est le pourcentage applicable ?", "Quelles sont les exigences ?", "Quel est le délai applicable ?"]:
    OUT.append({"id": f"X{len(OUT) + 1:03d}", "split": "v5", "category": "ambigu", "question": q, "expect_clarify": True, "validated_by": V, "synthetic": False})
# ---------------------------------------------------------------- Arabe -> texte (question arabe ; passage français ou arabe de l'acte attendu)
for q, w in [("ما هو المبلغ السنوي الأقصى لحق الصرف للسفر إلى الخارج المعمول به حاليا؟", "INS-07-26"),
             ("ما هي التزامات المشاركين في أنظمة الدفع بخصوص سرية وسلامة المعلومات؟", "REG-05-07"),
             ("على أي مستحقات تتكون الاحتياطيات الإلزامية للبنوك حسب النظام رقم 2004-02؟", "REG-04-02"),
             ("ما هي نسبة العلاوة المستحقة على البنوك لفائدة صندوق ضمان الودائع البنكية سنة 2020؟", "INS-13-20")]:
    assert w in fr_works or w in ar_works, w
    OUT.append({"id": f"X{len(OUT) + 1:03d}", "split": "v5", "category": "arabe", "question": q, "expected": [{"work_id": w, "article": None}],
                "any_language": True, "validated_by": V, "synthetic": False})

dst = HERE / "gold_v5.jsonl"
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    for r in OUT:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
sha = hashlib.sha256(dst.read_bytes()).hexdigest()
(HERE / "gold_v5.sha256").write_text(sha + "  gold_v5.jsonl\n", encoding="utf-8")
print(len(OUT), "questions", dict(Counter(r["category"] for r in OUT)))
print("sha256", sha)
