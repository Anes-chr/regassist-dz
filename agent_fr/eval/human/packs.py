"""Paquets de relecture HUMAINE (fichiers HTML locaux, sans réseau : rien ne quitte la machine) et intégration des verdicts.

1. review : benchmark -> review/benchmark_review.html (+ .csv). Le juriste valide chaque question : question claire, source officielle, article, passage, réponse attendue,
   état juridique à la date de référence. Export JSON (bouton) -> `ingest-review` met à jour validation_humaine et applique les corrections (historique conservé).
2. eval   : sorties du système (run_bench) -> review/human_eval.html : au moins 50 questions échantillonnées (stratifiées par type) ; l'évaluateur répond
   Source correcte / Article correct / Version correcte / Réponse correcte / Citation correcte / Hallucination (oui/non). `ingest-eval` compare à la notation
   automatique (accord, kappa, divergences) SANS modifier les règles de notation.
Usage :
  python -m agent_fr.eval.human.packs review --bench B.jsonl [--corpus DIR]
  python -m agent_fr.eval.human.packs ingest-review --bench B.jsonl --verdicts export.json
  python -m agent_fr.eval.human.packs eval --bench B.jsonl --runs results/human_bench_dev.json results/human_bench_test.json --n 60 [--seed 7]
  python -m agent_fr.eval.human.packs ingest-eval --bench B.jsonl --runs ... --verdicts export.json
"""
import argparse
import csv
import html
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
OUT = HERE / "review"

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
body{font:15px/1.5 system-ui,Segoe UI,sans-serif;max-width:1000px;margin:0 auto;padding:16px;background:#fafafa;color:#111}
.card{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px 16px;margin:14px 0}.k{color:#555;font-size:.85rem}
.q{font-size:1.1rem;font-weight:600}.src{background:#f3f6fb;border-left:3px solid #7aa;padding:6px 10px;margin:6px 0;white-space:pre-wrap;font-size:.92rem}
.warn{background:#fff4e5;border:1px solid #e0b060;padding:8px 12px;border-radius:8px}label{margin-right:14px}fieldset{border:1px solid #ccc;border-radius:8px;margin:8px 0}
textarea{width:100%;min-height:50px}button{padding:8px 14px;border-radius:8px;border:1px solid #888;background:#fff;cursor:pointer}.done{border-color:#2a7}
code{background:#eee;padding:1px 4px;border-radius:4px}.tag{display:inline-block;background:#eef;border-radius:6px;padding:1px 8px;margin-right:6px;font-size:.8rem}
</style></head><body>
<h1>__TITLE__</h1>
<div class="warn">__INTRO__<br><b>Confidentialité :</b> cette page fonctionne hors ligne ; aucune donnée n'est envoyée. Vos réponses sont enregistrées dans ce navigateur ; cliquez sur
« Exporter » pour obtenir un fichier à transmettre.</div>
<p><button onclick="exportAll()">Exporter les verdicts (JSON)</button> <span id="prog"></span></p>
<div id="app"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('data').textContent);const KEY='review::'+DATA.kind+'::'+DATA.stamp;
let V={};try{V=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(V))}catch(e){};prog()}
function prog(){const n=DATA.items.filter(i=>V[i.id]&&V[i.id].__done).length;document.getElementById('prog').textContent=n+' / '+DATA.items.length+' relues'}
function esc(s){const d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML}
function radios(id,name,opts){return opts.map(o=>`<label><input type=radio name="${id}_${name}" value="${o[0]}" ${(V[id]&&V[id][name]===o[0])?'checked':''} onchange="setv('${id}','${name}',this.value)"> ${o[1]}</label>`).join('')}
function setv(id,k,v){V[id]=V[id]||{};V[id][k]=v;V[id].__done=DATA.required.every(r=>V[id][r]!==undefined&&V[id][r]!=='');save();document.getElementById('c_'+id).classList.toggle('done',!!V[id].__done)}
function field(id,k,ph){return `<textarea placeholder="${ph}" oninput="setv('${id}','${k}',this.value)">${esc((V[id]&&V[id][k])||'')}</textarea>`}
const YN=[['oui','oui'],['non','non'],['nsp','ne sait pas']];
__JS__
document.getElementById('app').innerHTML=DATA.items.map(i=>`<div class="card ${(V[i.id]&&V[i.id].__done)?'done':''}" id="c_${i.id}">${DATA.render(i)}</div>`).join('');
function exportAll(){const out={kind:DATA.kind,stamp:DATA.stamp,exported_at:new Date().toISOString(),evaluateur:prompt('Nom de l\\'évaluateur / du juriste :')||'',verdicts:V};
const b=new Blob([JSON.stringify(out,null,1)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='verdicts_'+DATA.kind+'.json';a.click()}
prog();
</script></body></html>"""

REVIEW_JS = r"""
DATA.required=['verdict','question_ok','source_ok','reponse_ok','etat_ok'];
DATA.render=function(i){
 const src=(i.sources||[]).map(s=>`<div class="src"><b>${esc(s.titre)}</b> — article ${esc(s.article)} — <a href="${esc(s.url_pdf)}" target="_blank" rel="noopener noreferrer">PDF officiel</a> · <a href="${esc(s.url_site)}" target="_blank" rel="noopener noreferrer">page du site</a> (p. ${esc(s.page)})<br>« ${esc(s.citation)} »</div>`).join('');
 return `<div class="k">${esc(i.id)} · <span class="tag">${esc(i.split)}</span><span class="tag">${esc(i.type_de_question)}</span><span class="tag">${esc(i.langue)}</span><span class="tag">${esc(i.domaine)}</span><span class="tag">difficulté : ${esc(i.niveau_de_difficulte)}</span>${(i.sous_benchmark||[]).map(x=>'<span class="tag">'+esc(x)+'</span>').join('')}</div>
 <p class="q">${esc(i.question)}</p>
 <div><b>Comportement attendu :</b> ${esc(i.attendu_comportement)} · <b>Date de référence :</b> ${esc(i.date_de_reference)} · <b>Statut juridique attendu :</b> ${esc(i.statut_juridique)}</div>
 <div><b>Réponse attendue (rédigée par l'IA, À VALIDER) :</b> ${esc(i.reponse_attendue)}</div>
 <div class="k">Faits clés : ${esc(JSON.stringify(i.faits_cles||[]))}</div>
 ${src||'<div class="k">Aucune source attendue (refus ou clarification).</div>'}
 ${(i.versions_interdites&&i.versions_interdites.length)?'<div class="k">Versions qui NE doivent PAS être présentées : '+i.versions_interdites.map(v=>esc(v.work_id+' art. '+v.article+' ('+(v.raison||'')+')')).join(' ; ')+'</div>':''}
 <div class="k">Statut calculé par le système pour la source principale : ${esc(i.statut_calcule)} (à comparer à votre avis juridique)</div>
 <fieldset><legend>Votre relecture</legend>
 <div>Question claire et bien posée ? ${radios(i.id,'question_ok',YN)}</div>
 <div>Source officielle, article et passage corrects ? ${radios(i.id,'source_ok',YN)}</div>
 <div>Réponse attendue correcte ? ${radios(i.id,'reponse_ok',YN)}</div>
 <div>État juridique et date de référence corrects ? ${radios(i.id,'etat_ok',YN)}</div>
 <div>Verdict : ${radios(i.id,'verdict',[['valide','valider'],['corrige','valider avec corrections'],['rejete','rejeter']])}</div>
 ${field(i.id,'reponse_corrigee','Réponse attendue corrigée (si besoin)')}${field(i.id,'statut_corrige','Statut juridique correct (ACTIVE / MODIFIED / REPLACED / ABROGATED / HISTORICAL / UNKNOWN) et motif')}${field(i.id,'commentaire','Commentaire')}
 </fieldset>`};
"""

EVAL_JS = r"""
DATA.required=['source','article','version','reponse','citation','hallucination'];
DATA.render=function(i){
 const cited=new Set(i.citations||[]);
 const srcs=(i.sources||[]).map(s=>`<div class="src"><b>[${esc(s.id)}]${cited.has(s.chunk_id)?' (citée)':''}</b> ${esc(s.titre)} — art. ${esc(s.article)} — statut calculé : ${esc(s.statut_juridique)}<br>${esc(s.texte)}</div>`).join('');
 return `<div class="k">${esc(i.id)} · <span class="tag">${esc(i.type_de_question)}</span><span class="tag">${esc(i.split)}</span> date de référence : ${esc(i.date_de_reference)}</div>
 <p class="q">${esc(i.question)}</p>
 <div><b>Réponse du système :</b><div class="src">${esc(i.answer)}</div></div>
 <div class="k">Notes du système : ${esc((i.notes||[]).join(' | '))}</div>
 <details><summary>Passages donnés au modèle (${(i.sources||[]).length})</summary>${srcs}</details>
 <details><summary>Élément de comparaison (réponse attendue rédigée par l'IA — NON validée)</summary><div class="src">${esc(i.reponse_attendue)}</div></details>
 <fieldset><legend>Votre évaluation</legend>
 <div>Source correcte (le bon texte) ? ${radios(i.id,'source',YN)}</div>
 <div>Article correct ? ${radios(i.id,'article',YN)}</div>
 <div>Version juridique correcte (bonne période / bonne version) ? ${radios(i.id,'version',YN)}</div>
 <div>Réponse correcte ? ${radios(i.id,'reponse',YN)}</div>
 <div>Citation correcte ? ${radios(i.id,'citation',YN)}</div>
 <div>Hallucination (information absente des sources) ? ${radios(i.id,'hallucination',YN)}</div>
 ${field(i.id,'commentaire','Commentaire')}</fieldset>`};
"""


def build_page(title, intro, kind, items, js):
    data = {"kind": kind, "stamp": time.strftime("%Y%m%d%H%M%S"), "items": items}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = PAGE.replace("__TITLE__", html.escape(title)).replace("__INTRO__", intro).replace("__JS__", js).replace("__DATA__", payload)
    return page


def official_sources(it, corpus):
    out = []
    for ps in it.get("passage_attendu", []):
        c = corpus.find_passage(ps["work_id"], ps.get("article"), ps["citation"])
        d = corpus.docs.get(ps["work_id"], {})
        out.append({"titre": (c or {}).get("title") or d.get("title"), "article": ps.get("article"), "citation": ps["citation"], "page": (c or {}).get("page_number"),
                    "url_pdf": (c or {}).get("document_url") or d.get("document_url"), "url_site": (c or {}).get("source_url") or d.get("source_url")})
    return out


def cmd_review(a):
    from agent_fr.eval.human.bench import Corpus, computed_status, load
    corpus = Corpus(a.corpus)
    items = load(a.bench)
    view = []
    for it in items:
        v = dict(it)
        v["sources"] = official_sources(it, corpus)
        main = (it.get("passage_attendu") or [{}])[0]
        v["statut_calcule"] = computed_status(corpus, main.get("work_id"), main.get("article")) if main else None
        view.append(v)
    OUT.mkdir(exist_ok=True)
    page = build_page("Relecture juridique du benchmark RegAssist DZ",
                      "Vous relisez des questions et des réponses attendues <b>rédigées par une IA</b> à partir des textes officiels de la Banque d'Algérie. "
                      "Votre avis de juriste prime. Pour chaque question : source, article, passage, réponse attendue et état juridique à la date de référence.",
                      "benchmark_review", view, REVIEW_JS)
    (OUT / "benchmark_review.html").write_text(page, encoding="utf-8")
    with open(OUT / "benchmark_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "split", "type", "langue", "question", "reponse_attendue", "document", "article", "passage", "date_de_reference", "statut_attendu",
                    "VERDICT (valide/corrige/rejete)", "reponse_corrigee", "statut_corrige", "commentaire"])
        for v in view:
            s = v["sources"][0] if v["sources"] else {}
            w.writerow([v["id"], v["split"], v["type_de_question"], v["langue"], v["question"], v["reponse_attendue"], s.get("titre", ""), s.get("article", ""),
                        s.get("citation", ""), v["date_de_reference"], v["statut_juridique"], "", "", "", ""])
    print("écrit :", OUT / "benchmark_review.html", "et .csv")


def cmd_ingest_review(a):
    if Path(a.bench).resolve() == (HERE / "benchmark_v1_draft.jsonl").resolve():
        sys.exit("REFUSÉ (phase 4) : benchmark_v1_draft.jsonl contient TEST v1 et ne doit plus jamais être réécrit. Enregistrez les annotations avec "
                 "`python -m agent_fr.eval.human.annotations ingest --file <export.json>` (ajout seul, benchmark intact).")
    items = [json.loads(l) for l in open(a.bench, encoding="utf-8") if l.strip()]
    ver = json.loads(Path(a.verdicts).read_text(encoding="utf-8"))
    by = {i["id"]: i for i in items}
    n = defaultdict(int)
    for iid, v in ver["verdicts"].items():
        it = by.get(iid)
        if not it or not v.get("verdict"):
            continue
        it.setdefault("historique_corrections", []).append({"date": ver.get("exported_at"), "validateur": ver.get("evaluateur"),
                                                           "avant": {k: it.get(k) for k in ("question", "reponse_attendue", "statut_juridique")}, "verdict": v})
        if v.get("reponse_corrigee"):
            it["reponse_attendue"] = v["reponse_corrigee"]
        if v.get("statut_corrige"):
            it["statut_juridique_note_humaine"] = v["statut_corrige"]
        it["validation_humaine"] = {"statut": v["verdict"], "validateur": ver.get("evaluateur"), "date": ver.get("exported_at"), "commentaire": v.get("commentaire"),
                                    "details": {k: v.get(k) for k in ("question_ok", "source_ok", "reponse_ok", "etat_ok")}}
        n[v["verdict"]] += 1
    with open(a.bench, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print("verdicts intégrés :", dict(n), "| restent en attente :", sum(1 for i in items if i["validation_humaine"]["statut"] == "en_attente"))


def cmd_eval(a):
    from agent_fr.eval.human.bench import load
    bench = {i["id"]: i for i in load(a.bench)}
    recs = []
    for p in a.runs:
        recs += [r for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]]
    pool = [r for r in recs if bench[r["id"]]["attendu_comportement"] == "repondre" and r.get("mode") == "llm" and r.get("answer_found")]
    rnd = random.Random(a.seed)
    by_type = defaultdict(list)
    for r in pool:
        by_type[bench[r["id"]]["type_de_question"]].append(r)
    chosen, types = [], sorted(by_type)
    while len(chosen) < a.n and any(by_type.values()):
        for t in types:
            if by_type[t] and len(chosen) < a.n:
                chosen.append(by_type[t].pop(rnd.randrange(len(by_type[t]))))
    items = []
    for r in chosen:
        b = bench[r["id"]]
        srcs = [{"id": s["id"], "chunk_id": s["chunk_id"], "titre": (s.get("document_url") or "").split("/")[-1], "article": s["article"], "texte": s["texte"],
                 "statut_juridique": s.get("statut_juridique")} for s in r["sources"]]
        items.append({"id": r["id"], "type_de_question": b["type_de_question"], "split": b["split"], "question": b["question"], "date_de_reference": b["date_de_reference"],
                      "answer": r["answer"], "notes": r["notes"], "citations": r["citations"], "sources": srcs, "reponse_attendue": b["reponse_attendue"]})
    OUT.mkdir(exist_ok=True)
    page = build_page("Évaluation humaine des réponses du système", "Vous évaluez des réponses générées par le système local (Qwen) à partir des passages affichés. "
                      "Répondez oui / non à chaque critère ; « ne sait pas » est accepté.", "human_eval", items, EVAL_JS)
    (OUT / "human_eval.html").write_text(page, encoding="utf-8")
    (OUT / "human_eval_sample.json").write_text(json.dumps([i["id"] for i in items]), encoding="utf-8")
    print("écrit :", OUT / "human_eval.html", f"({len(items)} questions, graine {a.seed})")


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for x, y in pairs if x == y) / n
    px = sum(1 for x, _ in pairs if x) / n
    py = sum(1 for _, y in pairs if y) / n
    pe = px * py + (1 - px) * (1 - py)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def cmd_ingest_eval(a):
    from agent_fr.eval.human.bench import Corpus, load
    from agent_fr.eval.human.score import score_item
    bench = {i["id"]: i for i in load(a.bench)}
    recs = {}
    for p in a.runs:
        run = json.loads(Path(p).read_text(encoding="utf-8"))
        for r in run["records"]:
            recs[r["id"]] = r
    corpus = Corpus(a.corpus)
    ver = json.loads(Path(a.verdicts).read_text(encoding="utf-8"))
    yes = lambda x: True if x == "oui" else (False if x == "non" else None)
    mapping = {"source": "doc@1", "article": "article@1", "version": "C3", "reponse": "reponse_correcte", "citation": "citation_correcte", "hallucination": "hallucination"}
    pairs, div = defaultdict(list), []
    for iid, v in ver["verdicts"].items():
        if iid not in recs:
            continue
        sc = score_item(bench[iid], recs[iid], corpus)
        for hk, ak in mapping.items():
            h, au = yes(v.get(hk)), sc.get(ak)
            if h is None or au is None:
                continue
            pairs[hk].append((h, bool(au)))
            if h != bool(au):
                div.append({"id": iid, "critere": hk, "humain": h, "auto": bool(au), "commentaire": v.get("commentaire")})
    res = {"evaluateur": ver.get("evaluateur"), "n_questions": len(ver["verdicts"]), "criteres": {
        k: {"n": len(p), "accord": round(sum(1 for x, y in p if x == y) / len(p), 3), "kappa": kappa(p),
            "humain_oui": round(sum(1 for x, _ in p if x) / len(p), 3), "auto_oui": round(sum(1 for _, y in p if y) / len(p), 3)} for k, p in pairs.items() if p},
        "divergences": div}
    dst = ROOT / "agent_fr" / "eval" / "results" / "human_eval_agreement.json"
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["criteres"], ensure_ascii=False, indent=1))
    print("divergences :", len(div), "| écrit :", dst)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("review", "ingest-review", "eval", "ingest-eval"):
        s = sp.add_parser(name)
        s.add_argument("--bench", required=True)
        s.add_argument("--corpus", default=None)
        s.add_argument("--verdicts")
        s.add_argument("--runs", nargs="*", default=[])
        s.add_argument("--n", type=int, default=60)
        s.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    {"review": cmd_review, "ingest-review": cmd_ingest_review, "eval": cmd_eval, "ingest-eval": cmd_ingest_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
