"""Mesure de l'agent. Trois jeux de tests, tous explicitement étiquetés :

1. navigation (SYNTHÉTIQUE, généré automatiquement depuis les métadonnées) : « Que dit le règlement n° X ? » / « article N du … »
   -> vérifie la résolution des références. Ce n'est PAS un test de compréhension juridique.
2. gold_seed.jsonl (écrit à la main, réponses vérifiées dans les textes extraits, NON validé par un juriste) : questions de fond.
3. out_of_scope.jsonl : questions qui doivent être refusées.
Pour un vrai jeu d'évaluation, faire valider/étendre gold_seed.jsonl par un professionnel (champ validated_by).
"""
import json
import random
import re
from pathlib import Path

from .agent import get_index
from .answer import fr_date
from .retrieve import search

EVAL = Path(__file__).resolve().parent / "eval"


def _load(name):
    p = EVAL / name
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []


def navigation(idx, n_docs=150, n_arts=150, seed=7):
    rnd = random.Random(seed)
    works = {}
    for c in idx.chunks:
        if c.get("number") and c["document_type"] in ("règlement", "instruction", "loi", "ordonnance", "lignes_directrices"):
            works.setdefault(c["work_id"], c)
    ws = rnd.sample(sorted(works), min(n_docs, len(works)))
    ok_doc = miss = 0
    fails = []
    for w in ws:
        c = works[w]
        label = c["document_type"].replace("_", " ")
        r = search(idx, f"Que dit le {label} n° {c['number']} ?", k=6)
        good = r.found and any(h.chunk["work_id"] == w for h in r.hits)
        ok_doc += good
        if not good:
            fails.append({"q": f"{label} n° {c['number']}", "work_id": w, "reason": r.reason})
    arts = [c for c in idx.chunks if c.get("article") and c["unit_kind"] == "article" and c.get("number")
            and c["document_type"] in ("règlement", "instruction", "loi")]
    sample = rnd.sample(arts, min(n_arts, len(arts)))
    ok_art = 0
    for c in sample:
        r = search(idx, f"Que prévoit l'article {c['article']} du {c['document_type']} n° {c['number']} ?", k=6)
        good = r.found and any(h.chunk["work_id"] == c["work_id"] and h.chunk.get("article") == c["article"] for h in r.hits)
        ok_art += good
        if not good and len(fails) < 30:
            fails.append({"q": f"art. {c['article']} {c['document_type']} {c['number']}", "work_id": c["work_id"], "reason": r.reason})
    return {"documents": (ok_doc, len(ws)), "articles": (ok_art, len(sample)), "echecs": fails[:15]}


def gold(idx):
    rows = _load("gold_seed.jsonl")
    ok, fails = 0, []
    for r in rows:
        res = search(idx, r["question"], k=5)
        subs = [s.lower() for s in r["expected_title_contains"]]
        hit = res.found and any(all(s in h.chunk["title"].lower() for s in subs) for h in res.hits)
        if hit and r.get("expected_text_contains"):
            hit = any(r["expected_text_contains"].lower() in h.chunk["text"].lower() for h in res.hits)
        ok += hit
        if not hit:
            fails.append({"q": r["question"], "found": res.found,
                          "top": [f"{h.chunk['document_type']} {h.chunk['number']}" for h in res.hits[:3]]})
    return {"ok": ok, "total": len(rows), "echecs": fails}


def out_of_scope(idx):
    rows = _load("out_of_scope.jsonl")
    refused, fails = 0, []
    for r in rows:
        res = search(idx, r["question"], k=3)
        if not res.found:
            refused += 1
        else:
            fails.append({"q": r["question"], "top": [f"{h.chunk['document_type']} {h.chunk['number']}" for h in res.hits[:2]],
                          "note": r.get("note", "")})
    return {"refuses": refused, "total": len(rows), "echecs": fails}


def _norm(t):
    return " ".join((t or "").replace("’", "'").lower().split())


def gold_v2(idx):
    """Évalue la réponse AFFICHÉE (citations de answer.extractive), par jeu (dev/test) et par catégorie."""
    from .answer import extractive
    rows = _load("gold_v2.jsonl")
    per = {}
    detail = []
    for r in rows:
        res = search(idx, r["question"], k=6)
        out = extractive(idx, res, 5)
        cits = out["citations"]
        ok = {}
        if r.get("expect_refuse"):
            ok["refus"] = not out["found"]
        else:
            exp = r["expected"]
            def match(c):
                w = c["chunk_id"].split("::")[0].rsplit(".", 1)[0]
                return any(w == e["work_id"] and (e["article"] is None or str(c["article"]) == e["article"]) for e in exp)
            hit = [c for c in cits if match(c)]
            ok["present"] = bool(hit)
            ok["top1"] = bool(cits) and match(cits[0])
            if r.get("key_fact"):
                ok["fait_cle"] = any(_norm(r["key_fact"]) in _norm(c["extrait"]) for c in hit)
            if r.get("must_flag_superseded") is not None:
                bad = [c for c in cits if c["chunk_id"].split("::")[0].rsplit(".", 1)[0] in r["must_flag_superseded"] and not c["alerte"]]
                ok["anciens_textes_signales"] = not bad
            if r.get("expect_note_contains"):
                ok["avertissement_vigueur"] = any(r["expect_note_contains"] in n for n in out["notes"])
        for k, v in ok.items():
            per.setdefault((r["split"], r["category"], k), []).append(bool(v))
            per.setdefault((r["split"], "TOUT", k), []).append(bool(v))
        if not all(ok.values()):
            detail.append({"id": r["id"], "split": r["split"], "category": r["category"], "question": r["question"], "ko": [k for k, v in ok.items() if not v],
                           "affiche": [f"{c['texte']} {c['emplacement'] or ''}".strip() for c in cits[:4]]})
    table = {}
    for (sp, cat, k), v in per.items():
        table.setdefault(sp, {}).setdefault(cat, {})[k] = f"{sum(v)}/{len(v)}"
    return {"table": table, "echecs": detail}


def run_all():
    idx = get_index()
    nav, g, o = navigation(idx), gold(idx), out_of_scope(idx)
    print("== 1. Navigation (jeu SYNTHÉTIQUE : résolution des références)")
    print(f"   textes retrouvés : {nav['documents'][0]}/{nav['documents'][1]}   articles retrouvés : {nav['articles'][0]}/{nav['articles'][1]}")
    for f in nav["echecs"][:8]:
        print("   ✗", f)
    print("== 2. Questions de fond (gold_seed : vérifié dans les textes, NON validé par un juriste)")
    print(f"   corrects : {g['ok']}/{g['total']}")
    for f in g["echecs"]:
        print("   ✗", f)
    print("== 3. Hors périmètre (doivent être refusées)")
    print(f"   refusées : {o['refuses']}/{o['total']}")
    for f in o["echecs"]:
        print("   ✗ non refusée :", f)
    g2 = gold_v2(idx)
    print("== 4. gold_v2 : 47 questions relues par Claude contre les textes (PAS un juriste humain)")
    for sp in ("dev", "test", "holdout"):
        print(f"   [{sp}]", "  ".join(f"{cat}: " + ", ".join(f"{k} {v}" for k, v in m.items()) for cat, m in g2["table"].get(sp, {}).items() if cat == "TOUT"))
        for cat, m in g2["table"].get(sp, {}).items():
            if cat != "TOUT":
                print(f"        {cat:24}", ", ".join(f"{k} {v}" for k, v in m.items()))
    for f in g2["echecs"]:
        print("   ✗", f["id"], f["split"], f["category"], f["ko"], "|", f["question"][:70], "->", f["affiche"][:2])
    out = {"navigation": nav, "gold_seed": g, "out_of_scope": o, "gold_v2": g2}
    Path(__file__).resolve().parent.parent.joinpath("corpus", "reports", "agent_eval.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
