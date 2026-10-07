"""Notation du benchmark juridique à partir des sorties enregistrées (run_bench.py). Règles : voir l'en-tête de bench.py (fixées avant la première exécution).
Usage : python -m agent_fr.eval.human.score --bench BENCH.jsonl --run results/human_bench_TAG.json [--corpus DIR] [--out results/human_score_TAG.json]"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent_fr.eval.human.bench import Corpus, computed_status, fact_ok, norm_fact, norm_text  # noqa: E402

BAD = {"ABROGATED", "REPLACED", "HISTORICAL"}
NUM = re.compile(r"\d[\d\s., ]*\d|\d")
ARTN = re.compile(r"\barticles?\s+(\d{1,3}(?:\s*(?:bis|ter|quater))?)", re.I)
SIGNAL = re.compile(r"abrog|remplac|échue|echue|non déterminé|non determine|historique|version antérieure|ancienne? |statut", re.I)


def match(key, exp):
    return key[0] == exp["work_id"] and (exp.get("article") is None or key[1] == exp["article"])


INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def digits(s: str) -> set:
    out = set()
    for m in NUM.finditer(str(s).translate(INDIC)):
        d = re.sub(r"\D", "", m.group(0))
        if len(d) >= 2:
            out.add(d.lstrip("0") or "0")
    return out


def score_item(it: dict, rec: dict, corpus: Corpus) -> dict:
    out = {"id": it["id"], "type": it["type_de_question"], "split": it["split"], "comportement": it["attendu_comportement"]}
    beh = it["attendu_comportement"]
    if beh == "refuser":
        out["refus_correct"] = (not rec["answer_found"]) and not rec["clarify"] and not rec["answer_clarify"]
        out["reponse_correcte"] = out["refus_correct"]
        out["retrieval_correct"] = not rec["found"]
        out["hors_corpus_repondu"] = not out["refus_correct"]
        return out
    if beh == "clarifier":
        out["clarification_correcte"] = bool(rec["clarify"] or rec["answer_clarify"])
        out["reponse_correcte"] = out["clarification_correcte"]
        out["retrieval_correct"] = out["clarification_correcte"]
        return out
    exp = it["passage_attendu"]
    groups = [[{"work_id": e["work_id"], "article": e.get("article")}] + list(e.get("alternatives", [])) for e in exp]      # passage attendu OU alternative légitime déclarée à l'avance
    accept = it.get("versions_acceptables") or [x for g in groups for x in g]
    forb = it.get("versions_interdites") or []
    allmode = it["type_de_question"] in ("B_multi_textes", "F_comparaison") or it.get("mode") == "all"
    ret = [(r["work_id"], r["article"]) for r in rec["retrieved"]]
    pos = []
    for g in groups:
        pos.append(next((i + 1 for i, k in enumerate(ret) if any(match(k, e) for e in g)), None))
    rank = (max(pos) if all(pos) else None) if allmode else min((p for p in pos if p), default=None)
    out["rank"] = rank
    out["rank_succ"] = rank
    for k in (1, 3, 5, 10):
        out[f"R@{k}"] = bool(rank and rank <= k)
    out["mrr"] = 1 / rank if rank else 0.0
    docs_k = lambda k: {w for w, _ in ret[:k]}
    gdoc = lambda g, k: any(e["work_id"] in docs_k(k) for e in g)
    out["doc@1"] = all(gdoc(g, 1) for g in groups) if allmode else any(gdoc(g, 1) for g in groups)
    out["doc@5"] = all(gdoc(g, 5) for g in groups) if allmode else any(gdoc(g, 5) for g in groups)
    has_art = any(e.get("article") for e in exp)
    gart = lambda g, k: any(match(kk, e) for e in g for kk in ret[:k])
    out["article@1"] = (all(gart(g, 1) for g in groups) if allmode else any(gart(g, 1) for g in groups)) if has_art else None
    out["article@5"] = (all(gart(g, 5) for g in groups) if allmode else any(gart(g, 5) for g in groups)) if has_art else None
    # exactitude temporelle / juridique (questions avec date de référence)
    if it.get("date_de_reference") is not None and ret:
        top = ret[0]
        first_ok = next((i for i, k in enumerate(ret[:5]) if any(match(k, a) for a in accept)), None)
        first_forb = next((i for i, k in enumerate(ret[:5]) if any(match(k, f) for f in forb)), None)
        out["temporel@1"] = any(match(top, a) for a in accept) and not any(match(top, f) for f in forb)
        out["temporel_sans_interdite_devant"] = first_ok is not None and (first_forb is None or first_ok < first_forb)
        st = computed_status(corpus, top[0], top[1])
        out["juridique@1"] = (not any(match(top, f) for f in forb)) and (st not in BAD or it.get("statut_juridique") in BAD)
        out["statut_top1_calcule"] = st
    elif it.get("date_de_reference") is not None:
        out["temporel@1"] = out["juridique@1"] = False
    # contexte et réponse
    srcs = rec.get("sources", [])
    src_keys = [(s["work_id"], s["article"]) for s in srcs]
    if allmode:
        out["contexte_suffisant"] = all(any(match(k, e) for e in g for k in src_keys) for g in groups)
    else:
        out["contexte_suffisant"] = any(match(k, a) for a in accept for k in src_keys)
    out["retrieval_correct"] = bool(rank and rank <= 5)
    if rec["mode"] != "llm" or not rec["answer_found"]:
        out.update({"C1": False, "C2": False, "C3": False, "C4": False, "C5": True, "reponse_correcte": False, "citation_correcte": False,
                    "statut_correct": None, "hallucination": False, "refus_a_tort": rec["mode"] == "llm" and not rec["answer_found"]})
        return out
    ans = rec["answer"]
    cited = set(rec["citations"])
    cited_src = [s for s in srcs if s["chunk_id"] in cited] or srcs
    cited_keys = [(s["work_id"], s["article"]) for s in cited_src]
    facts = it.get("faits_cles", [])
    out["C1"] = all(fact_ok(ans, f) for f in facts) if facts else True
    ctext = norm_fact(" ".join(s["texte"] + " " + s.get("meta", "") for s in cited_src))        # une « source » = le bloc donné au modèle : passage + référence, titre, statut, relations
    out["C2"] = all(any(norm_fact(a) in ctext for a in (f if isinstance(f, list) else [f])) for f in facts) if facts else True
    out["C3"] = (not any(match(k, f) for f in forb for k in cited_keys)) and any(match(k, a) for a in accept for k in cited_keys)
    if allmode:
        out["C4"] = all(any(k[0] == e["work_id"] for e in g for k in cited_keys) for g in groups)
    else:
        out["C4"] = any(match(k, a) for a in accept for k in cited_keys)
    src_digits = set()
    for s in srcs:
        src_digits |= digits(s["texte"]) | digits(s.get("meta", ""))       # le modèle reçoit aussi la référence, la date, le titre et l'article de chaque source
    extra = digits(ans) - digits(it["question"]) - src_digits
    bad_art = [m for m in ARTN.findall(ans) if not any(str(m).lower() == str(s["article"]).lower() for s in srcs) and not re.search(r"article\s+" + re.escape(m), " ".join(s["texte"] for s in srcs), re.I)]
    out["C5"] = not extra and not bad_art
    out["nombres_hors_contexte"] = sorted(extra)[:6]
    out["articles_hors_contexte"] = bad_art[:4]
    out["citation_correcte"] = out["C4"]
    out["reponse_correcte"] = all(out[c] for c in ("C1", "C2", "C3", "C4", "C5"))
    out["hallucination"] = (not out["C5"]) or (not out["C2"])
    out["refus_a_tort"] = False
    if it.get("statut_juridique") is not None:
        if it.get("sujet"):                                          # abrogation : statut du texte INTERROGÉ
            st = computed_status(corpus, it["sujet"]["work_id"], it["sujet"].get("article"))
        else:
            ref = exp[-1] if allmode else exp[0]                      # multi-textes / comparaison : source la plus RÉCENTE (dernier passage attendu)
            main = next((s for s in cited_src if match((s["work_id"], s["article"]), ref)), None) or next((s for s in cited_src if any(match((s["work_id"], s["article"]), a) for a in accept)), cited_src[0] if cited_src else None)
            st = computed_status(corpus, main["work_id"], main["article"]) if main else None
        out["statut_calcule"] = st
        out["statut_correct"] = st == it["statut_juridique"]
        if it["statut_juridique"] not in ("ACTIVE", "MODIFIED"):
            out["statut_signale"] = bool(SIGNAL.search(ans) or any(SIGNAL.search(n) for n in rec["notes"]))
    # erreurs critiques (définies avant la mesure) : voir docs/RETRIEVAL_PHASE3.md
    out["erreur_temporelle_critique"] = bool(forb) and any(match(k, f) for f in forb for k in cited_keys) and not out["C3"] and it.get("date_de_reference") in ("actuel", None)
    return out


def aggregate(items: list[dict]) -> dict:
    def rate(xs, key):
        vals = [x[key] for x in xs if x.get(key) is not None]
        return (round(sum(1 for v in vals if v) / len(vals), 3), len(vals)) if vals else (None, 0)
    ans = [x for x in items if x["comportement"] == "repondre"]
    out = {"n": len(items), "n_repondre": len(ans)}
    for k in ("R@1", "R@3", "R@5", "R@10", "doc@1", "doc@5", "article@1", "article@5", "temporel@1", "juridique@1", "contexte_suffisant", "retrieval_correct",
              "C1", "C2", "C3", "C4", "C5", "reponse_correcte", "citation_correcte", "statut_correct", "hallucination", "refus_a_tort", "erreur_temporelle_critique"):
        out[k] = rate(ans, k)
    out["MRR"] = (round(sum(x["mrr"] for x in ans if "mrr" in x) / max(1, sum(1 for x in ans if "mrr" in x)), 3), len(ans))
    ref = [x for x in items if x["comportement"] == "refuser"]
    cla = [x for x in items if x["comportement"] == "clarifier"]
    out["refus_correct"] = rate(ref, "refus_correct")
    out["hors_corpus_repondu"] = rate(ref, "hors_corpus_repondu")
    out["clarification_correcte"] = rate(cla, "clarification_correcte")
    out["reponse_correcte_toutes"] = rate(items, "reponse_correcte")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    bench = {i["id"]: i for i in (json.loads(l) for l in open(a.bench, encoding="utf-8") if l.strip())}
    run = json.loads(Path(a.run).read_text(encoding="utf-8"))
    corpus = Corpus(a.corpus or run.get("corpus"))
    items = [score_item(bench[r["id"]], r, corpus) for r in run["records"]]
    res = {"run": a.run, "bench_sha256": run["bench_sha256"], "pipeline": run["pipeline"], "split": run["split"], "global": aggregate(items), "par_type": {}, "items": items}
    for t in sorted({x["type"] for x in items}):
        res["par_type"][t] = aggregate([x for x in items if x["type"] == t])
    tem = [x for x in items if bench[x["id"]].get("sous_benchmark") and "temporalite" in bench[x["id"]]["sous_benchmark"]]
    res["sous_benchmark_temporalite"] = aggregate(tem)
    dst = Path(a.out) if a.out else Path(a.run).with_name(Path(a.run).name.replace("human_bench_", "human_score_"))
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    g = res["global"]
    print(json.dumps({k: v for k, v in g.items()}, ensure_ascii=False))
    print("écrit :", dst)


if __name__ == "__main__":
    main()
