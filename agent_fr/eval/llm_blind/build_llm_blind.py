"""Construit le jeu AVEUGLE de comparaison LLM : Qwen3-4B de base VS futures versions (fine-tunées ou non).

RÈGLES (voir README.md) : ce jeu ne doit JAMAIS servir à l'entraînement. Il est accompagné d'un manifeste (empreintes + liste d'exclusion)
et d'un contrôle de fuite (leak_check.py) à exécuter sur tout futur jeu d'entraînement.
Les contextes « citation » et « je ne sais pas » sont de VRAIS passages du corpus (vérifiés mécaniquement) ; aucune donnée générée par Claude
n'est destinée à l'entraînement : ces items sont des tests écrits à la main.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys_chunks = {}
for l in open(ROOT / "corpus/chunks/chunks_fr.jsonl", encoding="utf-8"):
    c = json.loads(l)
    sys_chunks.setdefault((c["work_id"], c.get("article")), c)


def norm(s):
    return " ".join(s.replace("’", "'").lower().split())


ITEMS = []


def add(**kw):
    kw["id"] = f"B{len(ITEMS) + 1:03d}"
    ITEMS.append(kw)


# ---------- Français général
for p, kws in [
    ("Qu'est-ce que la masse monétaire ?", ["monnaie", "circulation", "agrégat", "liquidités"]),
    ("Explique la différence entre un chèque et un virement.", ["chèque", "virement", "ordre"]),
    ("Que signifie « blanchiment d'argent » ?", ["origine", "illicite", "fonds", "dissimul"]),
    ("À quoi sert un taux de change ?", ["monnaie", "devise", "valeur", "échange"]),
    ("Qu'est-ce qu'une banque commerciale ?", ["dépôts", "crédits", "clients", "prêt"]),
    ("Explique en deux phrases le rôle d'un commissaire aux comptes.", ["comptes", "audit", "certifi", "contrôle"]),
    ("Qu'est-ce que la diversification d'un portefeuille ?", ["risque", "actifs", "répart"]),
    ("Quelle est la différence entre un débit et un crédit en comptabilité ?", ["compte", "emploi", "ressource", "gauche", "droite", "débit"]),
]:
    add(cat="fr", prompt=p, expect_any=kws, max_arabic_ratio=0.05, min_words=20)

# ---------- Arabe général
for p, kws in [
    ("ما هي وظائف النقود؟", ["وسيط", "قياس", "قيمة", "مخزن", "ادخار"]),
    ("اشرح ما هو سعر الصرف.", ["عملة", "عملات", "سعر"]),
    ("ما المقصود بغسل الأموال؟", ["أموال", "مصدر", "غير مشروع", "إخفاء", "إخفاء"]),
    ("ما هو الفرق بين الشيك والتحويل المصرفي؟", ["شيك", "تحويل"]),
    ("ما هي فوائد فتح حساب مصرفي؟", ["حساب", "أمان", "مدخرات", "تحويل"]),
    ("عرّف الفائدة المصرفية بجملة واحدة.", ["فائدة", "قرض", "مبلغ"]),
    ("ما هو دور وزارة المالية في الاقتصاد؟", ["الميزانية", "الإنفاق", "الضرائب", "السياسة المالية"]),
]:
    add(cat="ar", prompt=p, expect_any=kws, min_arabic_ratio=0.6, min_words=8)
add(cat="ar", prompt="ترجم إلى الفرنسية: البنك المركزي يحافظ على استقرار الأسعار.", expect_any=["banque centrale"],
    expect_all_groups=[["prix"], ["stabilité", "stabilise", "stable"]], max_arabic_ratio=0.15)

# ---------- Instructions strictes
add(cat="instr", prompt="Réponds uniquement avec un objet JSON contenant les clés \"nom\" et \"age\" pour : Karim, 30 ans. Aucun autre texte.",
    json_keys=["nom", "age"], json_contains={"nom": "karim"}, json_number_in={"age": [30]})
add(cat="instr", prompt="Écris le mot « banque » en MAJUSCULES, sans rien d'autre.", regex_cs=["^\\s*BANQUE\\W*$"])
add(cat="instr", prompt="Donne exactement 5 mots sur le thème de la finance, séparés par des virgules, sans aucune phrase.",
    regex_all=["^\\s*[^,\\n]+(,\\s*[^,\\n]+){4}\\s*\\.?\\s*$"])
add(cat="instr", prompt="Réponds en français, en moins de 15 mots : pourquoi faut-il épargner ?", max_words=14, max_arabic_ratio=0.05)
add(cat="instr", prompt="Réponds uniquement avec un tableau JSON de 3 chaînes de caractères : trois devises. Aucun autre texte.", json_list_len=3, json_list_item_str=True)
add(cat="instr", prompt="Réponds uniquement par « VRAI » ou « FAUX » : 7 est un nombre pair.", regex_cs=["^\\s*FAUX\\W*$"])
add(cat="instr", prompt="Écris une liste numérotée (1., 2., 3.) de 3 étapes pour ouvrir un compte bancaire, sans introduction.",
    regex_all=["(?m)^\\s*1\\.", "(?m)^\\s*2\\.", "(?m)^\\s*3\\."])
add(cat="instr", prompt="أجب بكلمة واحدة فقط، «نعم» أو «لا»: هل الجزائر في أفريقيا؟", regex_cs=["^\\s*نعم\\W*$"])

# ---------- Citation d'une source (le modèle reçoit un vrai passage + la consigne de l'agent)
CITE = [
    (("INS-74-94", "8"), "À quel bilan se rapportent les fonds propres nets ?", "non consolidé"),
    (("REG-20-01-20200315", "2"), "Qu'entend-on par conditions de banque ?", "rémunération, les tarifs et les commissions"),
    (("INS-29-94", "5"), "Dans quel compte les avoirs en devises de l'importateur doivent-ils être situés ?", "compte devises intitulé"),
    (("INS-04-24", "6"), "Que doit s'assurer l'institution financière du donneur d'ordre pour un virement électronique national ?", "informations sur le donneur d'ordre"),
    (("REG-00-01", "22"), "Au profit de qui l'acte de nantissement est-il établi ?", "Banque d'Algérie"),
    (("INS-01-26-20260107", "2"), "À quel taux l'instruction fixe-t-elle les réserves obligatoires ?", "1%"),
    (("INS-08-26", "10"), "L'exportateur doit-il informer sa banque d'un événement affectant l'opération d'exportation ?", "sans délai"),
    (("INS-06-25", "28"), "Quelles règles le prestataire de services de paiement doit-il respecter pour protéger ses utilisateurs ?", "25-03"),
]
chunk_ids = []
for key, q, fact in CITE:
    c = sys_chunks[key]
    assert norm(fact) in norm(c["text"]), f"fait absent {fact} / {key}"
    chunk_ids.append(c["chunk_id"])
    add(cat="cite", question=q, context={"texte": f"{c['document_type'].capitalize()} n° {c['number']}", "article": c.get("article"),
                                         "page": c["page_number"], "statut": c["status"], "passage": c["text"][:1400]},
        key_fact=fact, expect_found=True, expect_cite="S1")

# ---------- « Je ne sais pas » : le passage fourni NE contient PAS la réponse
UNK = [
    (("INS-74-94", "8"), "Quel est le montant minimal du capital d'une banque ?"),
    (("REG-20-01-20200315", "2"), "Quelle est la sanction en cas de non-respect des conditions de banque ?"),
    (("INS-29-94", "5"), "Quel est le taux de change applicable aux comptes devises ?"),
    (("INS-04-24", "6"), "Quel est le plafond d'un virement électronique ?"),
    (("REG-00-01", "22"), "Quel est le taux du réescompte ?"),
    (("INS-01-26-20260107", "2"), "À partir de quelle date ce taux est-il appliqué ?"),
]
for key, q in UNK:
    c = sys_chunks[key]
    chunk_ids.append(c["chunk_id"])
    add(cat="unknown", question=q, context={"texte": f"{c['document_type'].capitalize()} n° {c['number']}", "article": c.get("article"),
                                            "page": c["page_number"], "statut": c["status"], "passage": c["text"][:1400]}, expect_found=False)
AR_CTX = "يتولى البنك المركزي إصدار العملة الوطنية والإشراف على المصارف والحفاظ على استقرار الأسعار."
add(cat="unknown", question="كم عدد موظفي البنك المركزي؟", context={"texte": "نص عام", "article": None, "page": 1, "statut": "STATUT À VÉRIFIER", "passage": AR_CTX}, expect_found=False)
add(cat="unknown", question="ما هو اسم محافظ البنك المركزي؟", context={"texte": "نص عام", "article": None, "page": 1, "statut": "STATUT À VÉRIFIER", "passage": AR_CTX}, expect_found=False)

out = HERE / "llm_blind_set.jsonl"
with open(out, "w", encoding="utf-8") as f:
    for it in ITEMS:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")
txt = out.read_bytes()
texts = sorted({it.get("prompt") or it["question"] for it in ITEMS})
manifest = {
    "set_sha256": hashlib.sha256(txt).hexdigest(), "n_items": len(ITEMS),
    "par_categorie": {c: sum(1 for i in ITEMS if i["cat"] == c) for c in sorted({i["cat"] for i in ITEMS})},
    "FORBIDDEN_FOR_TRAINING": True,
    "exclude_questions_normalized": [norm(t) for t in texts],
    "exclude_chunk_ids": sorted(set(chunk_ids)),
    "note": "Tout jeu d'entraînement doit passer leak_check.py : aucune question de ce jeu ni aucun de ces passages ne doit y figurer.",
}
(HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(ITEMS), "items", manifest["par_categorie"], "sha256", manifest["set_sha256"][:16])
