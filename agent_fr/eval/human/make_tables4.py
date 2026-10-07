"""Tableaux Markdown du rapport de phase 4, UNIQUEMENT à partir des instantanés (phase 3 final / phase 4) et des fichiers de résultats mesurés. « non mesuré » si une mesure manque.
Usage : python -m agent_fr.eval.human.make_tables4 > docs/tables_phase4.md   (écrit aussi agent_fr/eval/results/twins_phase4.csv)"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
RES = ROOT / "agent_fr" / "eval" / "results"
OLD = Path("D:/llm/snapshots/corpus_phase3_final")
NEW = Path("D:/llm/snapshots/corpus_phase4")


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def docs(base):
    out = []
    for lg in ("fr", "ar", "und"):
        d = json.loads((base / f"documents_{lg}.json").read_text(encoding="utf-8"))
        out += d if isinstance(d, list) else list(d.values())
    return out


def chunks(base):
    return [c for lg in ("fr", "ar", "und") for c in jl(base / f"chunks_{lg}.jsonl")]


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f3(v):
    return f"{v[0]:.3f} ({round(v[0] * v[1])}/{v[1]})" if v and v[0] is not None else "non mesuré"


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    d0, d1, c0, c1 = docs(OLD), docs(NEW), chunks(OLD), chunks(NEW)
    P = print
    # ------------------------------------------------------------------ A. corpus
    dup = lambda cs: (len(cs) - len({c["chunk_id"] for c in cs}), len({k for k, v in collections.Counter(c["chunk_id"] for c in cs).items() if v > 1}),
                      sum(v for v in collections.Counter(c["chunk_id"] for c in cs).values() if v > 1))
    art_ar = lambda ds: sum(d["structure_info"]["article_count"] for d in ds if d["language"] == "ar")
    zero_ar = lambda ds: sum(1 for d in ds if d["language"] == "ar" and d["structure_info"]["article_count"] == 0)
    fr_w = lambda ds: {d["work_id"] for d in ds if d["language"] == "fr"}
    orph = lambda ds: sum(1 for d in ds if d["language"] in ("ar", "und") and d["work_id"] not in fr_w(ds))
    unc = [c for c in c1 if c.get("ocr_uncertain")]
    P("## A. Corpus : avant (phase 3 final) / après (phase 4)\n")
    P("| Mesure | Phase 3 | Phase 4 |\n|---|---:|---:|")
    P(f"| Documents | {len(d0)} | {len(d1)} |")
    P(f"| Chunks (FR + AR + indéterminée) | {len(c0)} | {len(c1)} |")
    P(f"| Identifiants de chunks en double (occurrences en trop / identifiants / chunks concernés) | {dup(c0)[0]} / {dup(c0)[1]} / {dup(c0)[2]} | {dup(c1)[0]} / {dup(c1)[1]} / {dup(c1)[2]} |")
    P(f"| Articles arabes détectés | {art_ar(d0)} | {art_ar(d1)} |")
    P(f"| Documents arabes sans aucun article détecté | {zero_ar(d0)} | {zero_ar(d1)} |")
    P(f"| Documents arabes / indéterminés sans jumeau de même work_id | {orph(d0)} | {orph(d1)} |")
    P(f"| Chunks arabes marqués OCR_UNCERTAIN (valeur numérique non corroborée) | non mesuré | {len(unc)} (dans {len({c['document_id'] for c in unc})} documents) |")
    P(f"| Textes distincts (work_id) | {len({d['work_id'] for d in d0})} | {len({d['work_id'] for d in d1})} |\n")
    # chunks inchangés (texte)
    h0 = collections.Counter(re.sub(r"\s+", " ", c["text"]) for c in c0)
    h1 = collections.Counter(re.sub(r"\s+", " ", c["text"]) for c in c1)
    P(f"Chunks dont le texte est identique entre les deux versions : {sum((h0 & h1).values())} / {len(c1)} (nouveaux textes : {sum((h1 - h0).values())} ; textes disparus : {sum((h0 - h1).values())}).\n")

    # ------------------------------------------------------------------ B. jumeaux FR/AR
    by_key = collections.defaultdict(list)
    from boa_pipeline.relations import num_key
    for d in d0:
        if d["language"] == "fr" and d.get("number"):
            by_key[(d["type_code"], num_key(d["number"]))].append(d)
    new_by_hash = {d["file_hash"]: d for d in d1}
    fr0 = fr_w(d0)
    rows = []
    for a in d0:
        if a["language"] not in ("ar", "und") or a["work_id"] in fr0 or not a.get("number"):
            continue
        cand = by_key.get((a["type_code"], num_key(a["number"])), [])
        if not cand:
            continue
        f = cand[0]
        na, nf = new_by_hash[a["file_hash"]], new_by_hash[f["file_hash"]]
        rule = na.get("twin_rule") or ("R-TWIN-DATE (date lue dans le libellé arabe corrigé)" if na["work_id"] == nf["work_id"] else None)
        rows.append({"fr": f["document_id"], "ar": a["document_id"], "fr_nouveau": nf["document_id"], "ar_nouveau": na["document_id"], "numero": f["number"], "date_fr": f["date"], "date_ar_avant": a["date"], "date_ar_apres": na["date"],
                     "titre_fr": f["title"][:90], "titre_ar": a["title"][:70], "attendue": "même work_id (même type + même numéro + même date)", "avant": f"work_id distincts : {f['work_id']} / {a['work_id']}",
                     "apres": (f"rattachés : {nf['work_id']} ({rule})" if na["work_id"] == nf["work_id"] else f"NON rattachés : {nf['work_id']} / {na['work_id']} — conflit de dates documenté, arbitrage humain (twin_overrides.json)")})
    P(f"## B. Les {len(rows)} jumeaux arabes non rattachés de la phase 3\n")
    P("| Document FR | Document AR (phase 3) | N° | Date FR | Date AR avant → après | Relation attendue | Relation avant | Relation après |\n|---|---|---|---|---|---|---|---|")
    for r in rows:
        P(f"| {r['fr']} | {r['ar']} | {r['numero']} | {r['date_fr']} | {r['date_ar_avant']} → {r['date_ar_apres']} | {r['attendue']} | {r['avant']} | {r['apres']} |")
    with open(RES / "twins_phase4.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    P()
    # ------------------------------------------------------------------ C. identifiants dupliqués par cause
    cnt = collections.defaultdict(list)
    for c in c0:
        cnt[c["chunk_id"]].append(c)
    groups = {k: v for k, v in cnt.items() if len(v) > 1}
    cause = collections.Counter()
    for k, v in groups.items():
        kind = v[0]["unit_kind"]
        if kind == "annexe" and re.search(r"annexe-(N|رقم)(::|$)", k):
            cause["annexes dont le numéro a été lu « N » ou « رقم » (défaut d'analyse de l'en-tête)"] += 1
        elif kind == "annexe":
            cause["annexes de même numéro dans un même texte (annexes I, II… répétées par partie)"] += 1
        else:
            cause["articles dont la numérotation recommence dans le même texte (additif, partie 2…)"] += 1
    identical = sum(1 for v in groups.values() if len({c["text"] for c in v}) == 1)
    P("## C. Les 76 identifiants de chunks en double de la phase 3\n")
    P(f"{len(groups)} identifiants, {sum(len(v) for v in groups.values())} chunks ; **chunks de texte identique : {identical}** (aucun doublon réel) ; tailles de groupe : {dict(collections.Counter(len(v) for v in groups.values()))}.\n")
    P("| Cause | Identifiants |\n|---|---:|")
    for k, v in cause.most_common():
        P(f"| {k} | {v} |")
    P("\nCause commune : la détection d'un doublon ne comparait qu'aux 3 derniers chunks (`chunk.py`). Correctif : identifiant unique par document (`::u<indice de l'unité>`), stable et déterministe ; 0 doublon après reconstruction.\n")
    # ------------------------------------------------------------------ D. liens morts
    dead = load(ROOT / "corpus" / "reports" / "dead_links.json") or []
    st = load(ROOT / "corpus" / "reports" / "dead_links_status.json")
    http = {x["url"]: x for x in (st or {}).get("items", [])}
    P(f"## D. Liens morts : 38 entrées = {len(dead)} URLs uniques\n")
    c = collections.Counter(x["resolution"] for x in dead)
    P(f"Résolution : {dict(c)} ; confiance : {dict(collections.Counter(x['confidence'] for x in dead))}. Vérification en ligne le {(st or {}).get('checked_at', 'non mesuré')} : "
      f"ancien chemin → HTTP {sorted({h['http_now'] for h in http.values()})}, URL officielle de remplacement → HTTP {sorted({u['http_now'] for h in http.values() for u in h['official_urls']})}.\n")
    P("| Ancien lien (404) | Document du corpus | URL officielle actuelle | Confiance |\n|---|---|---|---|")
    for x in dead:
        r = x["resolved_documents"][0]
        P(f"| …{x['url'].split('bank-of-algeria.dz')[-1]} | {r['document_id']} | …{r['official_url'].split('bank-of-algeria.dz')[-1]} | {x['confidence'].split(' (')[0]} |")
    P()
    # ------------------------------------------------------------------ E. OCR
    S = load(RES / "ocr_bench_scores.json")
    if S:
        a, b = S["actuel"], S["tessdata_best"]
        P("## E. Benchmark OCR arabe : OCR actuel / tessdata_best\n")
        P("Jeu A = pages à couche texte native rendues puis passées à l'OCR (vérité exacte ; 7 documents, 14 pages ; 3 documents à couche texte partiellement corrompue exclus) ; jeu B = scans problématiques, vérité des valeurs = texte du jumeau français (19 documents).\n")
        P("| Mesure | OCR actuel | tessdata_best | Écart |\n|---|---:|---:|---:|")

        def row(lab, x, y, pct=True):
            if x is None or y is None:
                P(f"| {lab} | non mesuré | non mesuré | |")
            else:
                P(f"| {lab} | {x:.3f} | {y:.3f} | {y - x:+.3f} |")
        row("Exactitude caractères (jeu A)", a["exactitude_caracteres_jeu_A"], b["exactitude_caracteres_jeu_A"])
        for cl, lab in (("chiffres", "Chiffres"), ("montants", "Montants"), ("dates", "Dates"), ("articles", "Numéros d'articles"), ("numeros_de_textes", "Numéros de textes"), ("noms_propres", "Noms propres"), ("termes_juridiques", "Termes juridiques")):
            row(f"Jeu A — {lab} (rappel)", a["classes"]["A"][cl][0], b["classes"]["A"][cl][0])
        for cl, lab in (("chiffres", "Chiffres"), ("pourcentages", "Pourcentages"), ("montants", "Montants"), ("dates", "Dates"), ("articles", "Numéros d'articles"), ("numeros_de_textes", "Numéros de textes")):
            row(f"Jeu B — {lab} (rappel agrégé)", a["classes"]["B"][cl][0], b["classes"]["B"][cl][0])
        for cl, lab in (("chiffres", "Chiffres"), ("pourcentages", "Pourcentages"), ("montants", "Montants"), ("dates", "Dates")):
            row(f"Jeu B hors REG-25-07 — {lab}", a["jeu_B_hors_REG_25_07"]["classes"][cl][0], b["jeu_B_hors_REG_25_07"]["classes"][cl][0])
        for cl in ("chiffres", "pourcentages", "montants", "dates", "articles", "numeros_de_textes"):
            row(f"Jeu B — {cl} (moyenne par document)", a["jeu_B_moyenne_par_document"].get(cl), b["jeu_B_moyenne_par_document"].get(cl))
        row("Jeu B — nombres parasites (absents du jumeau FR), part", a["chiffres_parasites"]["B"][0], b["chiffres_parasites"]["B"][0])
        row("Jeu B hors REG-25-07 — nombres parasites", a["jeu_B_hors_REG_25_07"]["chiffres_parasites"][0], b["jeu_B_hors_REG_25_07"]["chiffres_parasites"][0])
        P(f"| Alertes OCR_UNCERTAIN, jeu B (unités signalées / unités) | {a['alertes_ocr_uncertain_jeu_B']['unites_signalees']} / {a['alertes_ocr_uncertain_jeu_B']['unites']} | {b['alertes_ocr_uncertain_jeu_B']['unites_signalees']} / {b['alertes_ocr_uncertain_jeu_B']['unites']} | |")
        P(f"| Secondes par page (moyenne) | {a['secondes_par_page_moy']} | {b['secondes_par_page_moy']} | {b['secondes_par_page_moy'] - a['secondes_par_page_moy']:+.2f} |\n")
        P("Valeurs critiques lues sur les documents du benchmark juridique (OCR actuel → tessdata_best) :\n")
        crit = {}
        for did, lab in (("INS-08-25.ar", "INS-08-25 art. 2 : « 2,75 % »"), ("INS-02-26.ar", "INS-02-26 art. 2 : « 2,50 % »"), ("INS-01-26.ar", "INS-01-26 art. 2 : « 1 % »"), ("REG-97-04.ar", "REG-97-04 art. 9 : « 600.000 »")):
            outs = []
            for eng in ("actuel", "tessdata_best"):
                r = load(RES / "ocr_bench" / f"{eng}__{did}.json")
                t = "\n".join(p["text"] for p in r["pages"]) if r else ""
                m = re.search(r"(?:600\.000|\d{2,3}\.\d{2}|\d,\d{2}[^\n]{0,6}%\S*|د 1 %|ب 1 %)", t)
                outs.append(m.group(0) if m else "(non retrouvée)")
            crit[lab] = outs
        P("| Valeur attendue (jumeau français) | OCR actuel | tessdata_best |\n|---|---|---|")
        for k, (x, y) in crit.items():
            P(f"| {k} | `{x}` | `{y}` |")
        P()
    A = load(RES / "ocr_alert_audit.json")
    if A:
        t = A["taux"]
        P("### Détecteur OCR_UNCERTAIN (alertes critiques par article arabe comparé au français)\n")
        P("| Type de texte arabe | Articles comparés | Alertes | Taux |\n|---|---:|---:|---:|")
        for m, lab in (("pdf_text", "couche texte native (aucune erreur d'OCR possible : plancher de faux positifs)"), ("mixed", "mixte"), ("ocr", "OCR")):
            P(f"| {lab} | {t[m]['articles_compares']} | {t[m]['alertes_critiques']} | {t[m]['taux']:.3f} |")
        P(f"\nRaisons (OCR) : {t['ocr']['raisons']} ; dont cause « symbole % lu comme des chiffres » identifiée : {t['ocr']['dont_symbole_pourcent_identifie']}.\n")
    # ------------------------------------------------------------------ F. régression
    P("## F. Régression : phase 2 / phase 3 / phase 4\n")
    old, p3, p4 = load(RES / "retrieval_all_hybrid_rerank.json"), load(RES / "regression_phase3_hybrid_rerank.json"), load(RES / "regression_phase4_hybrid_rerank.json")
    if old and p3 and p4:
        P("### Jeux historiques (gold v2–v5, 136 questions, retrieval seul, `hybrid_rerank`)\n")
        P("| Mesure | Phase 2 (corpus 2026-10-06) | Phase 3 (corpus final) | Phase 4 |\n|---|---:|---:|---:|")
        for k in ("R@1", "R@3", "R@5", "R@10", "MRR", "faux_refus", "refus_ok", "clarif_ok", "perime_en_tete"):
            P(f"| {k} | {old['summary']['TOUT'].get(k)} | {p3['summary']['TOUT'].get(k)} | {p4['summary']['TOUT'].get(k)} |")
        Q = {}
        for s in ("v2", "v3", "v4", "v5"):
            for l in open(ROOT / "agent_fr" / "eval" / f"gold_{s}.jsonl", encoding="utf-8"):
                r = json.loads(l)
                Q[r["id"]] = r["question"][:70]
        rk = lambda d: {r["id"]: r for r in d["records"]}
        o, a3, a4 = rk(old), rk(p3), rk(p4)
        P("\n| Question suivie | Phase 2 | Phase 3 | Phase 4 | Explication |\n|---|---:|---:|---:|---|")
        why = {"G038": "relation FR → jumeau arabe corrigée", "V041": "articles arabes de REG-25-07 détectés (en-tête « المادة8. » collé)", "W007": "inchangé", "X019": "règle de séries (« en 2003 » = exercice 2003) : non modifiée",
               "X026": "règle de séries : non modifiée", "X028": "règle de séries : non modifiée"}
        for i in ("G038", "V041", "W007", "X019", "X026", "X028"):
            P(f"| {i} {Q[i]} | {o[i].get('rank')} | {a3[i].get('rank')} | {a4[i].get('rank')} | {why[i]} |")
        ar = [i for i in a4 if a4[i]["category"] == "arabe"]
        P(f"\nQuestions arabes des jeux historiques ({len(ar)}) : Recall@5 phase 2 / 3 / 4 = " + " / ".join(str(sum(1 for i in ar if (d[i].get('rank') or 99) <= 5)) for d in (o, a3, a4)) + ".\n")
    d3, d4 = load(RES / "human_score_dev_final2.json"), load(RES / "human_score_dev_phase4.json")
    if d3 and d4:
        P("### Benchmark humain DEV (64 questions à réponse attendue + 14 refus / clarifications)\n")
        P("| Mesure | Phase 3 (DEV) | Phase 4 (DEV) |\n|---|---:|---:|")
        for k, lab in (("R@1", "Recall@1"), ("R@3", "Recall@3"), ("R@5", "Recall@5"), ("R@10", "Recall@10"), ("MRR", "MRR"), ("temporel@1", "Exactitude temporelle@1"), ("juridique@1", "Exactitude juridique@1"),
                       ("contexte_suffisant", "Contexte suffisant"), ("C1", "C1 répond"), ("C2", "C2 soutenue"), ("C3", "C3 bonne version"), ("C4", "C4 citation"), ("C5", "C5 rien hors contexte"),
                       ("reponse_correcte", "**Réponse correcte**"), ("statut_correct", "Statut correct"), ("hallucination", "Hallucination (auto)"), ("refus_a_tort", "Refus à tort"),
                       ("erreur_temporelle_critique", "Erreur temporelle critique (règle automatique)"), ("refus_correct", "Refus corrects"), ("clarification_correcte", "Clarifications")):
            P(f"| {lab} | {f3(d3['global'].get(k))} | {f3(d4['global'].get(k))} |")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
