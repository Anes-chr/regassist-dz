"""Construit gold_v2.jsonl. Chaque question est vérifiée MÉCANIQUEMENT : le passage attendu existe et contient le fait clé.
Relecture : effectuée par Claude (assistant IA) contre le texte extrait ; ce n'est PAS une validation par un juriste humain."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
chunks = {}
for l in open(ROOT / "corpus/chunks/chunks_fr.jsonl", encoding="utf-8"):
    c = json.loads(l)
    chunks.setdefault((c["work_id"], c.get("article")), []).append(c)

V = "Claude (relecture automatisée contre le texte extrait) — pas un juriste humain"
# (split, catégorie, question, [(work_id, article), ...], fait_clé)
Q = [
    # ---- DÉVELOPPEMENT (utilisé pour régler l'agent)
    ("dev", "fond", "Quelle part de ses fonds propres une banque peut-elle consacrer à une seule participation ?", [("REG-14-02", "19")], "15 %"),
    ("dev", "fond", "Quelle commission les banques perçoivent-elles pour la tenue des comptes en devises ?", [("INS-01-22", "6")], "0,50%"),
    ("dev", "fond", "Que comprend l'assiette des réserves obligatoires ?", [("INS-02-04", "2")], "dépôts à vue"),
    ("dev", "fond", "Le crédit intra-journalier de la Banque d'Algérie est-il payant ?", [("REG-05-04", "31")], "à titre gratuit"),
    ("dev", "fond", "Dans quel cas la régularisation d'un chèque sans provision est-elle refusée au titulaire du compte ?", [("INS-01-11-20110309", "16")], "douze (12) mois"),
    ("dev", "fond", "Dans quel cadre doivent être conclues les opérations de finance islamique sur le marché monétaire interbancaire ?", [("REG-25-13", "9")], "conventions-cadres"),
    ("dev", "fond", "Que peut faire la Banque d'Algérie pour se couvrir de ses créances douteuses ?", [("ORD-03-11", "55")], "nantissements"),
    ("dev", "fond", "Que se passe-t-il en cas de litige entre intermédiaires agréés sur une opération de change conclue entre eux ?", [("REG-17-01", "36")], "arbitrage de la Banque d’Algérie"),
    ("dev", "fond", "Un membre du comité de stabilité financière peut-il donner mandat à quelqu'un pour siéger à sa place ?", [("LOI-23-09", "160")], "ne peuvent en aucun cas donner mandat"),
    ("dev", "fond", "Peut-on échanger sans limite de montant les billets retirés de la circulation ?", [("REG-98-01", "2")], "sans limitation de montant"),
    ("dev", "fond", "Qui peut fixer le taux d'intérêt excessif ?", [("REG-09-03", "5")], "fixer le taux d'intérêt excessif"),
    ("dev", "relation", "Quelle instruction a modifié l'article 2 de l'instruction n° 09-96 sur le droit de change des étudiants à l'étranger ?", [("INS-07-00", "1")], "09-96"),
    ("dev", "fond", "Quelles qualités du dirigeant sont examinées pour son agrément ?", [("INS-04-25", "2")], "honorabilité"),
    ("dev", "fond", "Quels effets publics peuvent servir aux opérations de politique monétaire ?", [("REG-09-02", "6")], "bons du Trésor"),
    ("dev", "reference", "Quel délai les établissements ont-ils pour se conformer au règlement n° 25-07 ?", [("REG-25-07", "7")], "vingt-quatre (24) mois"),
    ("dev", "evolutif", "Quel est le plafond d'indemnisation par déposant ?", [("REG-20-03", "10")], "deux millions"),
    ("dev", "evolutif", "Quel montant maximal un voyageur peut-il sortir d'Algérie en espèces ?", [("REG-24-05-20241013", "2")], "sept mille cinq cent"),
    ("dev", "evolutif", "Quelle indemnité journalière de mission à l'étranger pour un cadre dirigeant d'entreprise ?", [("INS-02-24", "6")], "32000"),
    # ---- TEST (jamais utilisé pour régler l'agent)
    ("test", "fond", "À quel cours convertit-on les avoirs et engagements en devises dans les états périodiques ?", [("INS-03-11", "8")], "cours moyen"),
    ("test", "fond", "Quels cours s'appliquent aux achats à terme de devises avec décaissement immédiat de dinars ?", [("REG-91-07", "28")], "cours comptant"),
    ("test", "fond", "Qui a droit à l'ouverture d'un compte de dépôt en dinars ?", [("INS-03-12", "2")], "a droit à l’ouverture"),
    ("test", "fond", "Comment la banque prévient-elle les déposants que leurs dépôts sont indisponibles ?", [("REG-20-03", "16")], "lettre recommandée"),
    ("test", "fond", "Quel taux d'intérêt s'applique à une avance consentie sur un dépôt à terme ?", [("INS-07-95", "15")], "d'un point de pourcentage"),
    ("test", "fond", "Dans quelle monnaie les crédits sont-ils déclarés à la centrale des risques ?", [("INS-04-19", "10")], "dinars algériens"),
    ("test", "fond", "Qui l'organe exécutif doit-il informer des incidents significatifs de contrôle interne ?", [("REG-11-08", "69")], "organe délibérant"),
    ("test", "fond", "À qui s'appliquent les diligences d'identification prévues par l'instruction n° 04-2026 ?", [("INS-04-26", "2")], "client occasionnel"),
    ("test", "fond", "Quel cours de change s'applique aux éléments en devises à la date d'arrêté des comptes ?", [("REG-25-06", "8")], "cours au comptant"),
    ("test", "fond", "Les exportateurs reçoivent-ils toujours la totalité du produit de leurs exportations en devises ?", [("REG-91-13", "19")], "tout ou partie"),
    ("test", "fond", "Où sont versées les allocations médicales en devises ?", [("INS-83-92", "6")], "tout guichet bancaire"),
    ("test", "fond", "Un projet de coopérative d'épargne et de crédit peut-il faire de la publicité sur son agrément ?", [("REG-08-03", "6")], "ne doit pas faire l’objet de publicité"),
    ("test", "fond", "Un rejet bancaire est-il encore possible une fois le délai de rejet dépassé ?", [("REG-05-06", "29")], "n'est plus possible"),
    ("test", "fond", "Un prestataire de services de paiement est-il soumis aux règles de lutte contre le blanchiment ?", [("REG-25-02", "29")], "blanchiment"),
    ("test", "fond", "Quels comptes les banques utilisent-elles pour enregistrer les opérations de change ?", [("REG-94-18", "5")], "comptes de position de change"),
    ("test", "relation", "Quel article a été ajouté au règlement n° 91-09 pour permettre une dérogation temporaire ?", [("REG-95-04", "5")], "dérogation temporaire"),
    ("test", "reference", "Que dit l'article 4 du règlement n° 14-02 ?", [("REG-14-02", "4")], "25 %"),
    ("test", "reference", "Que prévoit l'article 5 du règlement n° 14-02 ?", [("REG-14-02", "5")], "huit (8) fois"),
    ("test", "evolutif", "À combien s'élève la garantie maximale des dépôts d'un client ?", [("REG-20-03", "10")], "deux millions"),
    ("test", "evolutif", "Combien d'euros un résident peut-il emporter à l'étranger par an ?", [("REG-24-05-20241013", "2")], "sept mille cinq cent"),
    # ---- HOLDOUT AVEUGLE : écrit après le réglage de l'agent, mesuré une seule fois, jamais utilisé pour le modifier
    ("holdout", "fond", "Comment doit être traitée une perte attendue sur des travaux d'Istisna'a en cours à la fin d'un exercice ?", [("REG-25-09", "60")], "comptabilisée dans le compte de résultats"),
    ("holdout", "fond", "En combien de compartiments la centrale des risques est-elle divisée ?", [("REG-12-01", "1")], "deux (2) compartiments"),
    ("holdout", "fond", "Que doit faire l'intermédiaire agréé en cas de retard dans l'exécution des mouvements de fonds avec l'étranger ?", [("REG-07-01-20070203", "40")], "saisir, sans délai, la Banque d'Algérie"),
    ("holdout", "fond", "Que doivent obtenir les banques avant d'entrer en relation avec une personne politiquement exposée ?", [("REG-12-03", "7")], "origine des capitaux"),
    ("holdout", "fond", "Les importations déjà expédiées avant la promulgation de l'instruction n° 05-2026 sont-elles concernées ?", [("INS-05-26", "7")], "ne s’appliquent pas"),
    ("holdout", "fond", "Qui approuve la procédure de communication financière des banques ?", [("REG-14-01", "35")], "organe délibérant"),
    ("holdout", "fond", "Vers où les revenus autorisés par la Banque d'Algérie peuvent-ils être transférés ?", [("INS-92-94", "6")], "compte devises"),
    ("holdout", "reference", "Quel est l'objet du règlement n° 2009-05 ?", [("REG-09-05", "1")], "états financiers"),
    ("holdout", "fond", "Comment étaient enregistrées les opérations de compensation en attendant la télé-compensation ?", [("REG-97-03", "17")], "supports dont les formes et conditions"),
    ("holdout", "fond", "Les banques peuvent-elles accorder de nouveaux crédits aux clients qui ont bénéficié d'un report d'échéance ?", [("INS-05-20", "5")], "peuvent consentir de nouveaux crédits"),
    ("holdout", "fond", "Qu'appelle-t-on actifs financiers détenus jusqu'à leur échéance ?", [("REG-09-08", "9")], "intention manifeste"),
    ("holdout", "fond", "Comment calcule-t-on le solde de liquidation quand une partie est défaillante ?", [("INS-79-95", "34")], "solde de liquidation"),
    ("holdout", "fond", "Que doivent vérifier les assujettis pour les agents et courtiers qui agissent pour le compte d'autrui ?", [("INS-02", "10")], "vérifier les pouvoirs"),
]

SUPERSEDED = {"plafond": ["REG-04-03", "REG-97-04"], "voyageur": ["REG-16-02"]}


def norm(s: str) -> str:
    return " ".join(s.replace("’", "'").lower().split())


OUT = []
for i, (split, cat, q, exp, fact) in enumerate(Q, 1):
    for w, a in exp:
        cs = chunks.get((w, a))
        assert cs, f"passage attendu introuvable : {w} art. {a}"
        assert any(norm(fact) in norm(c["text"]) for c in cs), f"fait clé absent : {fact!r} dans {w} art. {a}"
    row = {"id": f"G{i:03d}", "split": split, "category": cat, "question": q,
           "expected": [{"work_id": w, "article": a} for w, a in exp], "key_fact": fact,
           "validated_by": V, "synthetic": False}
    if cat == "evolutif":
        key = "plafond" if ("plafond" in q or "garantie" in q) else "voyageur" if ("voyageur" in q or "euros" in q) else None
        row["must_flag_superseded"] = SUPERSEDED.get(key, [])
    OUT.append(row)

TRAPS = [
    ("trap_texte_inexistant", "Que dit le règlement n° 99-99 ?"),
    ("trap_texte_inexistant", "Que prévoit l'article 12 de l'instruction n° 77-77 ?"),
    ("trap_article_inexistant", "Que dit l'article 400 du règlement n° 14-02 ?"),
    ("hors_sujet", "Quelle est la recette du couscous ?"),
    ("hors_sujet", "Comment installer Python sur Windows ?"),
    ("hors_sujet", "météo à Alger demain"),
    ("hors_sujet", "Quel est le cours de l'action Apple aujourd'hui ?"),
    ("hors_sujet", "Quel est le taux d'imposition des sociétés en France ?"),
]
TRAPS += [("hors_sujet", "Combien coûte un billet d'avion Alger-Paris ?"), ("trap_texte_inexistant", "Que dit l'article 3 du règlement n° 00-00 ?")]
for j, (cat, q) in enumerate(TRAPS, 1):
    OUT.append({"id": f"T{j:03d}", "split": "holdout" if j > 8 else "test", "category": cat, "question": q, "expect_refuse": True,
                "validated_by": V, "synthetic": False})
OUT.append({"id": "T101", "split": "test", "category": "temporel",
            "question": "Quel est le taux de réescompte actuellement en vigueur ?",
            "expected": [{"work_id": "INS-03-17", "article": None}], "expect_note_contains": "en vigueur",
            "validated_by": V, "synthetic": False,
            "note": "l'agent ne doit PAS affirmer qu'un taux est en vigueur : il doit signaler que le corpus ne le permet pas"})

with open(Path(__file__).parent / "gold_v2.jsonl", "w", encoding="utf-8") as f:
    for r in OUT:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(OUT), "questions écrites ; toutes vérifiées contre les passages attendus")
