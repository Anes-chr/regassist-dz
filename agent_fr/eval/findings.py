"""Rapport de constats pour relecture humaine (juriste) — généré automatiquement par un assistant IA, à confirmer.
Sortie : corpus/reports/legal_review_findings.md"""
import difflib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
docs = json.loads((ROOT / "corpus/metadata/documents_fr.json").read_text(encoding="utf-8"))
chunks = [json.loads(l) for l in open(ROOT / "corpus/chunks/chunks_fr.jsonl", encoding="utf-8")]
audit = json.loads((ROOT / "corpus/reports/citation_audit_fr.json").read_text(encoding="utf-8"))
by_doc = defaultdict(list)
for c in chunks:
    by_doc[c["document_id"]].append(c)
text_of = {d: "\n".join(c["text"] for c in cs) for d, cs in by_doc.items()}

L = []
w = L.append
w("# Constats pour relecture juridique — corpus français Banque d'Algérie\n")
w("> Généré par un assistant IA (Claude). **Ce n'est pas une validation par un juriste humain** : chaque constat est une piste à confirmer sur le PDF officiel.\n")

w("## 1. Traçabilité des citations")
w(f"- {audit['chunks']} passages non-OCR vérifiés contre les PDF d'origine : **{audit['ok']} identiques à la page annoncée**, "
  f"{audit['page_ok_but_edge_differs']} avec une différence en bordure (césure / en-tête), {audit['not_found']} introuvables.")
w(f"- {audit['ocr_skipped']} passages issus d'OCR **non vérifiables automatiquement** : contrôle humain requis.")
w("- La « page » citée est la **page du PDF** (pas la pagination imprimée du texte, ex. loi 23-09 : page PDF 12 = page imprimée 7).\n")

w("## 2. Textes évolutifs (modifiés / abrogés par d'autres textes du corpus)")
rel = Counter()
for d in docs:
    for k in ("modifie_par", "complete_par", "abroge_par", "remplace_par"):
        if d.get(k):
            rel[k] += 1
w(f"- Textes ayant au moins une modification/abrogation connue : modifiés {rel['modifie_par']}, complétés {rel['complete_par']}, "
  f"abrogés {rel['abroge_par']}, remplacés {rel['remplace_par']}.")
w(f"- Statut « abrogé » affirmé (preuve dans l'intitulé d'un texte officiel) : {sum(1 for d in docs if d['status'] == 'abrogé')}. "
  f"Tous les autres : « STATUT À VÉRIFIER ». **Le site ne publie aucun statut de vigueur.**")
unres = sum(len(d.get("unresolved_references", [])) for d in docs)
w(f"- Références à des textes absents du corpus (relations non résolues) : {unres} — un texte cité mais non collecté peut en modifier un autre.")
w("- **Risque principal** : une question simple peut tomber sur la version d'origine d'un texte modifié (ex. plafond de garantie des dépôts : "
  "600 000 DA en 2004, 2 000 000 DA depuis 2018/2020). L'agent affiche alors une alerte et remonte le texte modificateur ; "
  "ce mécanisme dépend de la détection des relations (voir §5).\n")

w("## 3. Incohérences entre le libellé du site et le document")
inc = [d for d in docs if any(f.startswith("incoherence_libelle_vs_document") for f in d["quality_flags"])]
w(f"{len(inc)} documents. Le pipeline conserve les deux valeurs, sans correction silencieuse.\n")
w("| Document | Libellé du site | Document (en-tête) | Champ |")
w("|---|---|---|---|")
for d in sorted(inc, key=lambda x: x["document_id"])[:40]:
    for f in d["quality_flags"]:
        if f.startswith("incoherence"):
            fld = f.split(":")[1]
            a = d.get("label_date") if fld == "date" else d.get("label_number")
            b = d["date"] if fld == "date" else d["number"]
            w(f"| {d['document_id']} | {a} | {b} | {fld} |")
w("")

w("## 4. Textes en double (deux fichiers pour le même texte) : différences de CHIFFRES")
pairs = defaultdict(list)
for d in docs:
    pairs[(d["work_id"], d["language"])].append(d["document_id"])
rows = []
def num(t):
    t = re.sub(r"\s*%", "%", t.replace(" ", " "))          # « 3,75 % » == « 3,75% »
    t = re.sub(r"(?<=\d)[ .](?=\d{3}(?!\d))", "", t)               # séparateurs de milliers : « 2.000.000 » == « 2 000 000 »
    return Counter(re.findall(r"\d+(?:,\d+)?%?", t))
for (wid, lg), ids in pairs.items():
    if len(ids) < 2 or not all(i in text_of for i in ids):
        continue
    a, b = ids[0], ids[1]
    ta, tb = text_of[a], text_of[b]
    wa, wb = ta.split(), tb.split()
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    ratio = sm.ratio() if len(wa) * len(wb) < 4e7 else sm.quick_ratio()   # gros textes : approximation (borne haute)
    na, nb = num(ta), num(tb)
    diff = (na - nb) + (nb - na)
    # on écarte les numéros de textes cités (14-02 / 2014-02) : un chiffre isolé ≥ 3 chiffres ou un pourcentage reste suspect
    sus = [k for k in diff if ("%" in k or len(re.sub(r"\D", "", k)) >= 4) and not re.fullmatch(r"(19|20)\d\d", k.strip())]
    rows.append((len(sus), 1 - ratio, wid, a, b, sorted(sus)[:6]))
w(f"{len(rows)} textes présents en deux fichiers (chemins `/2021/…` et `/2023/…`). Classés par nombre de chiffres divergents :\n")
w("| Texte | Fichiers | Similarité | Chiffres qui diffèrent |")
w("|---|---|---|---|")
for n, dr, wid, a, b, sus in sorted(rows, reverse=True)[:25]:
    w(f"| {wid} | {a} / {b} | {1 - dr:.0%} | {', '.join(sus) or '—'} |")
same = sum(1 for r in rows if r[0] == 0)
w(f"\n{same}/{len(rows)} paires n'ont aucun chiffre significatif divergent (différences probablement typographiques ou de mise en page).\n")

w("## 4 bis. Documents signalés pour contrôle humain")
fl = Counter(f.split(":")[0] for d in docs for f in d["quality_flags"])
for k, v in fl.most_common():
    w(f"- `{k}` : {v}")
w("")

w("## 5. Limites de l'automatisation à faire confirmer")
w("- Les relations (modifie / abroge / complète / remplace) sont extraites par motifs lexicaux : l'intitulé donne une preuve forte, le corps du texte une preuve à vérifier. "
  "Une abrogation implicite (« toutes dispositions contraires ») n'est pas résolue.")
w("- Un texte « abrogé par » un autre peut l'être partiellement : le drapeau `partial` existe mais sa fiabilité n'est pas mesurée.")
w("- Les copies `/2021/` et `/2023/` : le corpus ne dit pas laquelle fait foi.")
w("- Les questions de test (`agent_fr/eval/gold_v2.jsonl`) sont relues par un assistant IA, pas par un juriste : champ `validated_by`.\n")

(ROOT / "corpus/reports/legal_review_findings.md").write_text("\n".join(L), encoding="utf-8")
print("écrit : corpus/reports/legal_review_findings.md", len(L), "lignes")
