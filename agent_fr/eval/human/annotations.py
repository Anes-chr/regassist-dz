"""Annotations HUMAINES (juriste) : enregistrement fidèle, recalcul séparé, aucune règle de recherche modifiée.

Principes (phase 4) :
  * le système ENREGISTRE ce que le juriste a répondu, rien de plus : les annotations vont dans `annotations/*.jsonl` (ajout seul, empreintes, évaluateur, date) ; le benchmark, les sorties
    gelées de TEST v1 et les règles de notation ne sont JAMAIS ouverts en écriture ;
  * aucune annotation n'est transformée automatiquement en règle de recherche, de contexte ou de notation ;
  * le juriste distingue CORRECT / INCORRECT / AMBIGU / QUESTION_MAL_FORMULEE / SOURCE_INCORRECTE / REPONSE_ATTENDUE_INCORRECTE : une question jugée mal conçue n'est pas comptée comme un échec
    du modèle (elle est listée à part, jamais supprimée du benchmark) ; pour une question de type G (ambiguë à dessein), « AMBIGU » est la validation attendue ;
  * pour les réponses : hallucination = non / juridique / factuelle / metadonnee_interne / nsp ; la « métadonnée interne » (ex. date de référence de la consigne reprise dans la réponse) est
    présentée à part et n'entre pas dans le taux d'hallucination humaine : c'est au juriste de la qualifier ;
  * le seuil d'hallucination n'est PAS modifié : il est lu dans decision_criteria.md (empreinte vérifiée).

Usage :
  python -m agent_fr.eval.human.annotations ingest --file verdicts_benchmark_review_p4.json
  python -m agent_fr.eval.human.annotations ingest --file verdicts_human_eval_p4.json
  python -m agent_fr.eval.human.annotations report [--out agent_fr/eval/results/human_validation_report]"""
import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ANN = HERE / "annotations"
BENCH = HERE / "benchmark_v1_draft.jsonl"
RESULTS = ROOT / "agent_fr" / "eval" / "results"
CRITERIA = HERE / "decision_criteria.md"
CRITERIA_SHA = HERE / "decision_criteria.md.sha256"

YNN = {"oui", "non", "nsp"}
CLASSES = {"CORRECT", "INCORRECT", "AMBIGU", "QUESTION_MAL_FORMULEE", "SOURCE_INCORRECTE", "REPONSE_ATTENDUE_INCORRECTE"}
HALLU = {"non", "juridique", "factuelle", "metadonnee_interne", "nsp"}
SCHEMAS = {
    "benchmark_review_p4": {"required": {"question_ok": YNN, "source_ok": YNN, "article_ok": YNN, "reponse_ok": YNN, "date_ok": YNN, "classe": CLASSES}, "optional": ["reponse_corrigee", "statut_corrige", "commentaire"],
                            "file": "benchmark_review.jsonl"},
    "human_eval_p4": {"required": {"source": YNN, "article": YNN, "version": YNN, "reponse": YNN, "citation": YNN, "justifiee": YNN, "hallucination": HALLU}, "optional": ["commentaire"],
                      "file": "answer_eval.jsonl"},
}
# seuils pré-enregistrés (decision_criteria.md, écrit avant TEST v1) : lus ici pour AFFICHAGE, jamais ajustés
THRESHOLDS = {"hallucination_go": 0.05, "hallucination_conditional_go": 0.10, "hallucination_no_go_above": 0.10}
AUTO_MAP = {"source": "doc@1", "article": "article@1", "version": "C3", "reponse": "reponse_correcte", "citation": "citation_correcte", "hallucination": "hallucination"}


# ------------------------------------------------------------------ fiches (CSV) : cas critiques et arbitrage des jumeaux FR/AR
SHEETS = {
    "cas_critiques": {
        "key": "cas", "file": "cas_critiques.jsonl", "known": {"H120", "H129", "H130"},
        "required": {"juriste": None, "question_juridiquement_valide": YNN, "source_retrouvee_pertinente": YNN, "reponse_juridiquement_correcte": YNN, "version_temporelle_correcte": YNN,
                     "citation_correcte": YNN, "hallucination": HALLU, "le_systeme_aurait_du_refuser": YNN,
                     "qualification": {"erreur_juridique_critique", "erreur_juridique_non_critique", "reponse_hors_sujet", "refus_a_tort", "refus_attendu", "non_erreur", "autre"}},
        "optional": ["commentaire"], "comment_required_if": ("qualification", {"autre"}),
    },
    "arbitrage_jumeaux": {
        "key": "texte", "file": "arbitrage_jumeaux.jsonl", "known": {"REG-90-01", "REG-02-01", "REG-06-01"},
        "required": {"juriste": None, "reference_correcte": {"FR", "AR", "DEUX_TEXTES_DISTINCTS", "INDETERMINE"}},
        "optional": ["date_de_reference_retenue", "commentaire"], "comment_required_if": ("reference_correcte", {"DEUX_TEXTES_DISTINCTS", "INDETERMINE"}),
    },
}


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for x, y in pairs if x == y) / n
    px, py = sum(1 for x, _ in pairs if x) / n, sum(1 for _, y in pairs if y) / n
    pe = px * py + (1 - px) * (1 - py)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def load_jsonl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


# ------------------------------------------------------------------ ingestion
def ingest(export_path, bench_path=BENCH, ann_dir=ANN, runs=None):
    """Valide et AJOUTE les annotations d'un export du navigateur. Retourne un résumé. Refuse un fichier déjà ingéré, une valeur hors liste, un identifiant inconnu."""
    export_path, bench_path, ann_dir = Path(export_path), Path(bench_path), Path(ann_dir)
    ann_dir.mkdir(parents=True, exist_ok=True)
    raw = export_path.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    log = load_jsonl(ann_dir / "ingest_log.jsonl")
    if any(x["file_sha256"] == file_sha for x in log):
        raise ValueError(f"fichier déjà ingéré (sha256 {file_sha[:12]}…) : une annotation ne s'ajoute qu'une fois")
    data = json.loads(raw.decode("utf-8"))
    kind = data.get("kind")
    if kind not in SCHEMAS:
        raise ValueError(f"type d'export inconnu : {kind!r} (attendu : {', '.join(SCHEMAS)})")
    sch = SCHEMAS[kind]
    bench = {json.loads(l)["id"]: l for l in bench_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    rows, rejected, skipped = [], [], 0
    for iid, v in (data.get("verdicts") or {}).items():
        if not isinstance(v, dict) or not any(k in v for k in sch["required"]):
            skipped += 1
            continue
        if iid not in bench:
            rejected.append((iid, "identifiant inconnu du benchmark"))
            continue
        missing = [k for k in sch["required"] if v.get(k) in (None, "")]
        if missing:
            skipped += 1                                                       # relecture incomplète : non enregistrée (jamais complétée à la place du juriste)
            continue
        bad = [k for k, allowed in sch["required"].items() if v[k] not in allowed]
        if bad:
            rejected.append((iid, "valeur hors liste pour " + ", ".join(bad)))
            continue
        rows.append({"kind": kind, "item_id": iid, "evaluateur": data.get("evaluateur") or "", "exported_at": data.get("exported_at"),
                     "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_file_sha256": file_sha, "bench_item_sha256": hashlib.sha256(bench[iid].encode("utf-8")).hexdigest(),
                     "annotation": {k: v[k] for k in list(sch["required"]) + sch["optional"] if k in v}})
    if rejected:
        raise ValueError(f"{len(rejected)} annotation(s) rejetée(s), rien n'est enregistré : {rejected[:5]}")
    if not (data.get("evaluateur") or "").strip():
        raise ValueError("nom de l'évaluateur absent : une annotation humaine doit être attribuée")
    with open(ann_dir / sch["file"], "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {"kind": kind, "enregistrees": len(rows), "incompletes_ignorees": skipped, "file_sha256": file_sha, "evaluateur": data.get("evaluateur")}
    with open(ann_dir / "ingest_log.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({**summary, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False) + "\n")
    return summary


def ingest_sheet(csv_path, ann_dir=ANN):
    """Enregistre une fiche CSV remplie par le juriste (cas critiques ou arbitrage FR/AR). Mêmes garanties que `ingest` : ajout seul, valeurs contrôlées, fichier déjà ingéré refusé, jamais
    de valeur complétée à la place du juriste ; l'arbitrage n'est PAS appliqué au corpus (twin_overrides.json reste une décision humaine explicite)."""
    import csv
    csv_path, ann_dir = Path(csv_path), Path(ann_dir)
    ann_dir.mkdir(parents=True, exist_ok=True)
    raw = csv_path.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    if any(x["file_sha256"] == file_sha for x in load_jsonl(ann_dir / "ingest_log.jsonl")):
        raise ValueError(f"fichier déjà ingéré (sha256 {file_sha[:12]}…)")
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines(), delimiter=";"))
    if not rows:
        raise ValueError("fiche vide")
    kind = next((k for k, sch in SHEETS.items() if sch["key"] in rows[0]), None)
    if kind is None:
        raise ValueError("fiche non reconnue (colonne « cas » ou « texte » attendue)")
    sch = SHEETS[kind]
    out, skipped = [], 0
    for r in rows:
        key = (r.get(sch["key"]) or "").strip()
        vals = {k: (r.get(k) or "").strip() for k in list(sch["required"]) + sch["optional"]}
        if not any(vals[k] for k in sch["required"] if k != "juriste"):
            skipped += 1                                                      # ligne non remplie : ignorée, jamais complétée
            continue
        if key not in sch["known"]:
            raise ValueError(f"identifiant inconnu : {key!r}")
        missing = [k for k in sch["required"] if not vals[k]]
        if missing:
            raise ValueError(f"{key} : champ(s) obligatoire(s) vide(s) : {', '.join(missing)}")
        bad = [k for k, allowed in sch["required"].items() if allowed and vals[k] not in allowed]
        if bad:
            raise ValueError(f"{key} : valeur hors liste pour {', '.join(bad)}")
        fld, trig = sch["comment_required_if"]
        if vals[fld] in trig and not vals.get("commentaire"):
            raise ValueError(f"{key} : un commentaire est obligatoire quand {fld} = {vals[fld]}")
        out.append({"kind": kind, "item": key, "juriste": vals["juriste"], "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_file_sha256": file_sha,
                    "annotation": {k: v for k, v in vals.items() if k != "juriste" and v}})
    with open(ann_dir / sch["file"], "a", encoding="utf-8", newline="\n") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {"kind": kind, "enregistrees": len(out), "lignes_vides_ignorees": skipped, "file_sha256": file_sha}
    with open(ann_dir / "ingest_log.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({**summary, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False) + "\n")
    return summary


# ------------------------------------------------------------------ recalcul
def latest(rows):
    """Dernière annotation par (item, évaluateur)."""
    out = {}
    for r in rows:
        out[(r["item_id"], r["evaluateur"])] = r
    return list(out.values())


def recompute(bench_path=BENCH, ann_dir=ANN, score_files=None):
    bench = {i["id"]: i for i in load_jsonl(bench_path)}
    ann_dir = Path(ann_dir)
    rev = latest(load_jsonl(ann_dir / "benchmark_review.jsonl"))
    ev = latest(load_jsonl(ann_dir / "answer_eval.jsonl"))
    rep = {"avertissement": "Annotations enregistrées telles quelles ; recalcul séparé ; aucune règle de recherche, de contexte ou de notation n'est modifiée par ce rapport.",
           "benchmark_sha256": sha(bench_path), "n_items_benchmark": len(bench)}
    # ---- A. validation du benchmark
    by_item = defaultdict(list)
    for r in rev:
        by_item[r["item_id"]].append(r)
    classes, excluded, disagreements = Counter(), {}, []
    for iid, rs in by_item.items():
        cl = {r["annotation"]["classe"] for r in rs}
        if len(cl) > 1:
            disagreements.append({"item": iid, "classes": sorted(cl), "evaluateurs": [r["evaluateur"] for r in rs]})
        r = rs[-1]
        c = r["annotation"]["classe"]
        classes[c] += 1
        is_g = bench[iid]["type_de_question"].startswith("G")
        ok = c == "CORRECT" or (is_g and c == "AMBIGU")                      # type G : « ambigu » est la validation attendue
        if not ok:
            excluded[iid] = {"classe": c, "type": bench[iid]["type_de_question"], "split": bench[iid]["split"], "commentaire": r["annotation"].get("commentaire")}
    n_ann = len(by_item)
    rep["validation_benchmark"] = {"items_annotes": n_ann, "couverture": round(n_ann / len(bench), 3) if bench else None, "par_classe": dict(classes),
                                   "questions_a_ne_pas_compter_comme_echec_du_modele": excluded, "desaccords_entre_evaluateurs": disagreements,
                                   "note": "Ces questions sont listées à part ; elles ne sont ni supprimées ni corrigées dans le benchmark gelé (TEST v1 intact)."}
    # ---- B. évaluation des réponses
    autos = {}
    for p in (score_files or [RESULTS / "human_score_dev_final2.json", RESULTS / "human_score_test_final.json"]):
        if Path(p).exists():
            for it in json.loads(Path(p).read_text(encoding="utf-8"))["items"]:
                autos[it["id"]] = it
    ev_by = {}
    for r in ev:
        ev_by.setdefault(r["item_id"], r)                                    # une ligne par question (premier évaluateur) ; les autres évaluateurs sont comptés à part
    n_eval = len(ev_by)
    used = {i: r for i, r in ev_by.items() if i not in excluded}
    h = Counter(r["annotation"]["hallucination"] for r in used.values())
    judged = sum(h[k] for k in ("non", "juridique", "factuelle", "metadonnee_interne"))
    real = h["juridique"] + h["factuelle"]
    rate = real / judged if judged else None
    crit = {}
    for k in ("source", "article", "version", "reponse", "citation", "justifiee"):
        vals = [r["annotation"][k] for r in used.values() if r["annotation"][k] in ("oui", "non")]
        crit[k] = {"n": len(vals), "oui": sum(1 for v in vals if v == "oui"), "taux_oui": round(sum(1 for v in vals if v == "oui") / len(vals), 3) if vals else None}
    # divergences automatique / humain
    pairs, div = defaultdict(list), []
    for iid, r in used.items():
        a = autos.get(iid)
        if not a:
            continue
        for hk, ak in AUTO_MAP.items():
            hv = r["annotation"][hk]
            if hk == "hallucination":
                hv = {"non": False, "juridique": True, "factuelle": True, "metadonnee_interne": False}.get(hv)       # la métadonnée interne n'est pas comptée comme hallucination humaine
            else:
                hv = {"oui": True, "non": False}.get(hv)
            av = a.get(ak)
            if hv is None or av is None:
                continue
            pairs[hk].append((hv, bool(av)))
            if hv != bool(av):
                div.append({"item": iid, "critere": hk, "humain": hv, "auto": bool(av), "commentaire": r["annotation"].get("commentaire")})
    agree = {k: {"n": len(p), "accord": round(sum(1 for x, y in p if x == y) / len(p), 3), "kappa": kappa(p)} for k, p in pairs.items() if p}
    correct_but_auto_wrong = [d["item"] for d in div if d["critere"] == "reponse" and d["humain"] and not d["auto"]]
    incorrect_but_auto_right = [d["item"] for d in div if d["critere"] == "reponse" and not d["humain"] and d["auto"]]
    auto_hallu_not_human = [d["item"] for d in div if d["critere"] == "hallucination" and d["auto"] and not d["humain"]]
    human_hallu_not_auto = [d["item"] for d in div if d["critere"] == "hallucination" and d["humain"] and not d["auto"]]
    meta_items = [i for i, r in used.items() if r["annotation"]["hallucination"] == "metadonnee_interne"]
    rep["evaluation_reponses"] = {
        "reponses_evaluees": n_eval, "dont_exclues_question_mal_conçue": n_eval - len(used), "reponses_retenues": len(used), "criteres_humains": crit,
        "hallucination_humaine": {"repartition": dict(h), "juridique": h["juridique"], "factuelle": h["factuelle"], "metadonnee_interne_a_part": h["metadonnee_interne"],
                                  "non_tranche_nsp": h["nsp"], "denominateur": judged, "taux_hallucination_humaine_juridique_ou_factuelle": round(rate, 3) if rate is not None else None,
                                  "intervalle_wilson_95": wilson(real, judged),
                                  "seuils_preenregistres": THRESHOLDS,
                                  "position_par_rapport_aux_seuils": None if rate is None else ("au-dessus du seuil NO-GO (> 10 %)" if rate > THRESHOLDS["hallucination_no_go_above"] else
                                                                                               "entre 5 % et 10 % (CONDITIONAL GO possible)" if rate > THRESHOLDS["hallucination_go"] else "≤ 5 %"),
                                  "avertissement": "Taux calculé sur l'ÉCHANTILLON évalué (stratifié par type), pas sur toutes les réponses ; le seuil n'est pas modifié."},
        "presentation_separee": {
            "hallucination_juridique": [i for i, r in used.items() if r["annotation"]["hallucination"] == "juridique"],
            "hallucination_factuelle": [i for i, r in used.items() if r["annotation"]["hallucination"] == "factuelle"],
            "metadonnee_interne": meta_items,
            "reponse_correcte_mais_notation_automatique_incorrecte": correct_but_auto_wrong,
            "reponse_incorrecte_mais_notation_automatique_correcte": incorrect_but_auto_right,
            "hallucination_automatique_non_confirmee_par_le_juriste": auto_hallu_not_human,
            "hallucination_confirmee_par_le_juriste_non_vue_par_la_notation_automatique": human_hallu_not_auto},
        "accord_automatique_humain": agree, "divergences": div}
    # ---- C. « validation humaine complète » au sens de decision_criteria.md
    cas = {}
    for r in latest([dict(x, item_id=x["item"], evaluateur=x["juriste"]) for x in load_jsonl(ann_dir / "cas_critiques.jsonl")]):
        cas[r["item"]] = {**r["annotation"], "juriste": r["juriste"]}
    arb = {r["item"]: {**r["annotation"], "juriste": r["juriste"]} for r in latest([dict(x, item_id=x["item"], evaluateur=x["juriste"]) for x in load_jsonl(ann_dir / "arbitrage_jumeaux.jsonl")])}
    rep["cas_critiques"] = {"qualifications_du_juriste": cas, "divergence_notation_automatique_vs_analyse_qualitative":
                            "H129 : la notation automatique ne compte pas l'erreur comme temporelle critique (article cité ≠ article listé comme version interdite) ; la qualification du juriste ci-dessus fait foi, "
                            "la règle de notation n'est pas modifiée." if "H129" in cas else "en attente de la qualification du juriste (H120, H129)"}
    rep["arbitrage_jumeaux_fr_ar"] = {"decisions_du_juriste": arb, "application": "non appliquée automatiquement : seul `confirmed` dans boa_pipeline/twin_overrides.json est lu par le pipeline"}
    rep["validation_humaine_complete"] = {"definition": "≥ 90 % du benchmark annoté ET ≥ 50 réponses évaluées par un humain", "benchmark_couvert": rep["validation_benchmark"]["couverture"],
                                          "reponses_evaluees": n_eval, "atteinte": bool(n_ann >= 0.9 * len(bench) and n_eval >= 50)}
    rep["decision_criteria_sha256_ok"] = (sha(CRITERIA) == CRITERIA_SHA.read_text().split()[0]) if CRITERIA.exists() and CRITERIA_SHA.exists() else None
    return rep


def to_markdown(rep) -> str:
    v, e = rep["validation_benchmark"], rep["evaluation_reponses"]
    L = ["# Validation humaine — recalcul (annotations du juriste, enregistrées sans interprétation automatique)", "",
         f"Benchmark : {rep['n_items_benchmark']} questions ; annotées : {v['items_annotes']} ({v['couverture']}) ; validation humaine complète : **{rep['validation_humaine_complete']['atteinte']}**", "",
         "## Classification des questions", "", "| Classe | n |", "|---|---:|"] + [f"| {k} | {n} |" for k, n in sorted(v["par_classe"].items())]
    L += ["", f"Questions à ne pas compter comme échec du modèle : {len(v['questions_a_ne_pas_compter_comme_echec_du_modele'])} (listées dans le JSON ; jamais supprimées).", "",
          "## Réponses évaluées", "", f"Évaluées : {e['reponses_evaluees']} ; retenues : {e['reponses_retenues']} ; exclues (question mal conçue) : {e['dont_exclues_question_mal_conçue']}", "",
          "| Critère humain | n | oui |", "|---|---:|---:|"] + [f"| {k} | {c['n']} | {c['taux_oui']} |" for k, c in e["criteres_humains"].items()]
    hh = e["hallucination_humaine"]
    L += ["", "## Hallucination (humaine), présentée séparément", "", "| Catégorie | n |", "|---|---:|", f"| hallucination juridique | {hh['juridique']} |", f"| hallucination factuelle | {hh['factuelle']} |",
          f"| métadonnée interne (à part) | {hh['metadonnee_interne_a_part']} |", f"| non tranché | {hh['non_tranche_nsp']} |", "",
          f"Taux d'hallucination humaine (juridique + factuelle) : **{hh['taux_hallucination_humaine_juridique_ou_factuelle']}** sur {hh['denominateur']} réponses jugées ; IC95 % {hh['intervalle_wilson_95']} ; "
          f"{hh['position_par_rapport_aux_seuils']}. {hh['avertissement']}", "", "## Automatique / humain", ""]
    for k, ids in e["presentation_separee"].items():
        L.append(f"* {k.replace('_', ' ')} : {len(ids)} {ids[:12] if ids else ''}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("ingest")
    s.add_argument("--file", required=True)
    s = sp.add_parser("ingest-sheet")
    s.add_argument("--file", required=True)
    s = sp.add_parser("report")
    s.add_argument("--out", default=str(RESULTS / "human_validation_report"))
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "ingest":
        print(json.dumps(ingest(a.file), ensure_ascii=False, indent=1))
    elif a.cmd == "ingest-sheet":
        print(json.dumps(ingest_sheet(a.file), ensure_ascii=False, indent=1))
    else:
        rep = recompute()
        Path(a.out + ".json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        Path(a.out + ".md").write_text(to_markdown(rep), encoding="utf-8")
        print(to_markdown(rep))


if __name__ == "__main__":
    main()
