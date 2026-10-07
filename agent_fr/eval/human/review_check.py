"""Contrôle TECHNIQUE (lecture seule) des deux interfaces officielles de relecture : review/benchmark_review_p4.html et review/human_eval_p4.html. Elles ne sont jamais modifiées par ce contrôle.
Vérifie : toutes les questions apparaissent (130), toutes les réponses apparaissent (60, mot pour mot celles des sorties gelées), les classifications et critères demandés sont disponibles, les annotations sont
persistantes (localStorage + export JSON), aucune annotation ne touche la source ni le benchmark (aucun accès réseau ni écriture dans la page), aucun score automatique n'est montré à l'évaluateur.
Usage : python -m agent_fr.eval.human.review_check   (code de sortie 1 si un contrôle échoue)"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEW = HERE / "review"
RESULTS = ROOT / "agent_fr" / "eval" / "results"
BENCH = HERE / "benchmark_v1_draft.jsonl"
SAMPLE = REVIEW / "human_eval_sample.json"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def extract(path):
    html = Path(path).read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    return html, json.loads(m.group(1).replace("<\\/", "</"))


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def check(review=REVIEW, bench_path=BENCH, results=RESULTS) -> dict:
    out, bad = {}, []

    def ok(name, cond, detail=""):
        out[name] = {"ok": bool(cond), "detail": detail}
        if not cond:
            bad.append(name)

    bench = {i["id"]: i for i in jl(bench_path)}
    # ---------------- benchmark_review_p4
    html, data = extract(Path(review) / "benchmark_review_p4.html")
    items = {i["id"]: i for i in data["items"]}
    ok("benchmark.toutes_les_questions", set(items) == set(bench) and len(items) == 130, f"{len(items)} questions dans la page, {len(bench)} dans le benchmark")
    ok("benchmark.texte_identique", all(items[i]["question"] == bench[i]["question"] and items[i]["reponse_attendue"] == bench[i]["reponse_attendue"] for i in bench), "question et réponse attendue identiques au benchmark")
    ok("benchmark.sources_presentes", all(len(items[i].get("sources") or []) == len(bench[i]["passage_attendu"]) for i in bench), "une source officielle (PDF + page du site) par passage attendu")
    classes = ["CORRECT", "INCORRECT", "AMBIGU", "QUESTION_MAL_FORMULEE", "SOURCE_INCORRECTE", "REPONSE_ATTENDUE_INCORRECTE"]
    ok("benchmark.classifications_disponibles", all(c in html for c in classes), "six classes proposées")
    ok("benchmark.champs_demandes", all(f in html for f in ("question_ok", "source_ok", "article_ok", "reponse_ok", "date_ok", "classe")) and "DATA.required=['question_ok','source_ok','article_ok','reponse_ok','date_ok','classe']" in html, "5 questions oui/non/nsp + classe obligatoires")
    # ---------------- human_eval_p4
    html2, data2 = extract(Path(review) / "human_eval_p4.html")
    sample = json.loads(Path(SAMPLE).read_text(encoding="utf-8"))
    recs = {}
    for f in ("human_bench_dev_final2.json", "human_bench_test_final.json"):
        for r in json.loads((Path(results) / f).read_text(encoding="utf-8"))["records"]:
            recs[r["id"]] = r
    it2 = {i["id"]: i for i in data2["items"]}
    ok("reponses.toutes_les_reponses", list(it2) == sample and len(it2) == 60, f"{len(it2)} réponses dans la page, échantillon de la phase 3 : {len(sample)}")
    ok("reponses.texte_identique_aux_sorties_gelees", all(it2[i]["answer"] == recs[i]["answer"] and it2[i]["citations"] == recs[i]["citations"] for i in sample), "réponse et citations identiques mot pour mot aux sorties gelées")
    ok("reponses.passages_donnes_au_modele", all(len(it2[i]["sources"]) == len(recs[i]["sources"]) for i in sample), "tous les passages donnés au modèle sont affichés")
    ok("reponses.criteres_et_hallucination", all(f in html2 for f in ("source", "article", "version", "reponse", "citation", "justifiee", "hallucination")) and all(
        c in html2 for c in ("'non'", "'juridique'", "'factuelle'", "'metadonnee_interne'", "'nsp'")), "7 critères ; hallucination : non / juridique / factuelle / métadonnée interne / ne sait pas")
    forbidden_keys = {"score", "reponse_correcte", "hallucination", "C1", "C2", "C3", "C4", "C5", "rank", "refus_a_tort"}
    ok("reponses.aucun_score_automatique", not any(forbidden_keys & set(i) for i in data2["items"]), "aucune clé de notation automatique dans les données de la page")
    # ---------------- persistance et export, absence de réseau / d'écriture
    for name, h in (("benchmark", html), ("reponses", html2)):
        ok(f"{name}.persistance_locale", "localStorage.setItem" in h and "localStorage.getItem" in h and "try{localStorage" in h, "annotations conservées dans le navigateur (try/catch si le stockage est bloqué)")
        ok(f"{name}.export_sans_perte", "exportAll" in h and "JSON.stringify(out,null,1)" in h and "verdicts:V" in h and "evaluateur" in h, "export JSON de TOUS les verdicts avec le nom de l'évaluateur")
        ok(f"{name}.aucun_reseau", not re.search(r"fetch\(|XMLHttpRequest|WebSocket|navigator\.sendBeacon|<script[^>]+src=|<link[^>]+href=|@import|import\(", h), "la page ne contacte aucun serveur ; les liens vers les PDF officiels sont de simples <a>")
        ok(f"{name}.aucune_ecriture_source", "FileSystem" not in h and "showSaveFilePicker" not in h and "indexedDB" not in h, "aucun accès disque : la seule sortie est le fichier exporté")
    return {"ok": not bad, "echecs": bad, "controles": out, "empreintes": {"benchmark_review_p4.html": sha(Path(review) / "benchmark_review_p4.html"), "human_eval_p4.html": sha(Path(review) / "human_eval_p4.html")}}


def main():
    rep = check()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    for k, v in rep["controles"].items():
        print(("OK  " if v["ok"] else "ÉCHEC"), k, "—", v["detail"])
    print(json.dumps(rep["empreintes"], indent=1))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
