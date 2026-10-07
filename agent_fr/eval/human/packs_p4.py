"""Paquets de relecture HUMAINE, schéma de la phase 4 (fichiers HTML locaux, hors ligne : rien ne quitte la machine). Les fichiers de la phase 3 (review/benchmark_review.html et
review/human_eval.html) ne sont PAS remplacés ; ces paquets sont écrits à côté, avec les classes demandées au juriste :
  benchmark : question correcte ? source attendue ? article attendu ? réponse attendue ? date de référence ? + CORRECT / INCORRECT / AMBIGU / QUESTION MAL FORMULÉE / SOURCE INCORRECTE / RÉPONSE ATTENDUE INCORRECTE ;
  réponses  : source ? article ? version juridique ? réponse ? citation ? hallucination (non / juridique / factuelle / métadonnée interne) ? réponse suffisamment justifiée ?
Aucun score automatique n'est affiché à l'évaluateur. Le fichier exporté est enregistré par `annotations.py ingest` (ajout seul ; le benchmark n'est jamais modifié).
Usage :
  python -m agent_fr.eval.human.packs_p4 review --corpus D:/llm/snapshots/corpus_phase3_final
  python -m agent_fr.eval.human.packs_p4 eval --runs agent_fr/eval/results/human_bench_dev_final2.json agent_fr/eval/results/human_bench_test_final.json   (même échantillon de 60 que la phase 3)"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from agent_fr.eval.human.packs import build_page, official_sources, OUT  # noqa: E402

BENCH = HERE / "benchmark_v1_draft.jsonl"
SAMPLE = OUT / "human_eval_sample.json"

REVIEW_JS = r"""
DATA.required=['question_ok','source_ok','article_ok','reponse_ok','date_ok','classe'];
const CLASSES=[['CORRECT','CORRECT'],['INCORRECT','INCORRECT'],['AMBIGU','AMBIGU'],['QUESTION_MAL_FORMULEE','QUESTION MAL FORMULÉE'],['SOURCE_INCORRECTE','SOURCE INCORRECTE'],['REPONSE_ATTENDUE_INCORRECTE','RÉPONSE ATTENDUE INCORRECTE']];
DATA.render=function(i){
 const src=(i.sources||[]).map(s=>`<div class="src"><b>${esc(s.titre)}</b> — article ${esc(s.article)} — <a href="${esc(s.url_pdf)}" target="_blank" rel="noopener noreferrer">PDF officiel</a> · <a href="${esc(s.url_site)}" target="_blank" rel="noopener noreferrer">page du site</a> (p. ${esc(s.page)})<br>« ${esc(s.citation)} »</div>`).join('');
 return `<div class="k">${esc(i.id)} · <span class="tag">${esc(i.split)}</span><span class="tag">${esc(i.type_de_question)}</span><span class="tag">${esc(i.langue)}</span><span class="tag">${esc(i.domaine)}</span><span class="tag">difficulté : ${esc(i.niveau_de_difficulte)}</span></div>
 <p class="q">${esc(i.question)}</p>
 <div><b>Comportement attendu :</b> ${esc(i.attendu_comportement)} · <b>Date de référence :</b> ${esc(i.date_de_reference)} · <b>Statut juridique attendu :</b> ${esc(i.statut_juridique)}</div>
 <div><b>Réponse attendue (rédigée par l'IA, À VALIDER) :</b> ${esc(i.reponse_attendue)}</div>
 ${src||'<div class="k">Aucune source attendue (refus ou clarification).</div>'}
 <fieldset><legend>Votre relecture</legend>
 <div>1. La question est-elle correcte et bien posée ? ${radios(i.id,'question_ok',YN)}</div>
 <div>2. La source attendue est-elle correcte ? ${radios(i.id,'source_ok',YN)}</div>
 <div>3. L'article attendu est-il correct ? ${radios(i.id,'article_ok',YN)}</div>
 <div>4. La réponse attendue est-elle correcte ? ${radios(i.id,'reponse_ok',YN)}</div>
 <div>5. La date de référence est-elle correcte ? ${radios(i.id,'date_ok',YN)}</div>
 <div><b>Classement de la question :</b> ${radios(i.id,'classe',CLASSES)}</div>
 ${field(i.id,'reponse_corrigee','Réponse attendue corrigée (si besoin)')}${field(i.id,'statut_corrige','Statut juridique correct (ACTIVE / MODIFIED / REPLACED / ABROGATED / HISTORICAL / UNKNOWN) et motif')}${field(i.id,'commentaire','Commentaire')}
 <div class="k">Une question mal conçue n'est pas comptée comme un échec du système. Pour une question de type G (ambiguë à dessein), « AMBIGU » est la bonne réponse.</div>
 </fieldset>`};
"""

EVAL_JS = r"""
DATA.required=['source','article','version','reponse','citation','justifiee','hallucination'];
const HAL=[['non','non'],['juridique','oui — hallucination JURIDIQUE (règle, valeur, statut, texte inventés ou faux)'],['factuelle','oui — hallucination FACTUELLE (date, nombre, nom, article absents des sources)'],['metadonnee_interne','information venant d\'une métadonnée interne du système (ex. date de référence), pas des sources'],['nsp','ne sait pas']];
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
 <div>1. Source correcte (le bon texte) ? ${radios(i.id,'source',YN)}</div>
 <div>2. Article correct ? ${radios(i.id,'article',YN)}</div>
 <div>3. Version juridique correcte (bonne période, bonne version) ? ${radios(i.id,'version',YN)}</div>
 <div>4. Réponse correcte ? ${radios(i.id,'reponse',YN)}</div>
 <div>5. Citation correcte ? ${radios(i.id,'citation',YN)}</div>
 <div>6. Réponse suffisamment justifiée par les sources citées ? ${radios(i.id,'justifiee',YN)}</div>
 <div><b>7. Hallucination ?</b> ${radios(i.id,'hallucination',HAL)}</div>
 ${field(i.id,'commentaire','Commentaire (obligatoire pour toute hallucination ou métadonnée interne)')}</fieldset>`};
"""


def cmd_review(a):
    from agent_fr.eval.human.bench import Corpus, computed_status, load
    corpus = Corpus(a.corpus)
    view = []
    for it in load(str(BENCH)):
        v = dict(it)
        v["sources"] = official_sources(it, corpus)
        view.append(v)
    OUT.mkdir(exist_ok=True)
    page = build_page("Relecture juridique du benchmark RegAssist DZ — schéma phase 4",
                      "Vous relisez des questions et des réponses attendues <b>rédigées par une IA</b> à partir des textes officiels de la Banque d'Algérie. Votre avis de juriste prime ; "
                      "aucune de vos réponses ne modifie automatiquement le système ni le benchmark.", "benchmark_review_p4", view, REVIEW_JS)
    (OUT / "benchmark_review_p4.html").write_text(page, encoding="utf-8")
    with open(OUT / "benchmark_review_p4.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "split", "type", "langue", "question", "reponse_attendue", "document", "article", "passage", "date_de_reference", "statut_attendu",
                    "question_ok", "source_ok", "article_ok", "reponse_ok", "date_ok", "CLASSE", "reponse_corrigee", "statut_corrige", "commentaire"])
        for v in view:
            s = v["sources"][0] if v["sources"] else {}
            w.writerow([v["id"], v["split"], v["type_de_question"], v["langue"], v["question"], v["reponse_attendue"], s.get("titre", ""), s.get("article", ""), s.get("citation", ""),
                        v["date_de_reference"], v["statut_juridique"], "", "", "", "", "", "", "", "", ""])
    print("écrit :", OUT / "benchmark_review_p4.html", "et .csv (", len(view), "questions )")


def cmd_eval(a):
    from agent_fr.eval.human.bench import load
    bench = {i["id"]: i for i in load(str(BENCH))}
    recs = {}
    for p in a.runs:
        for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]:
            recs[r["id"]] = r
    ids = json.loads(SAMPLE.read_text(encoding="utf-8"))                       # MÊME échantillon de 60 que la phase 3 : aucun nouveau tirage
    items = []
    for iid in ids:
        r, b = recs[iid], bench[iid]
        srcs = [{"id": s["id"], "chunk_id": s["chunk_id"], "titre": (s.get("document_url") or "").split("/")[-1], "article": s["article"], "texte": s["texte"],
                 "statut_juridique": s.get("statut_juridique")} for s in r["sources"]]
        items.append({"id": iid, "type_de_question": b["type_de_question"], "split": b["split"], "question": b["question"], "date_de_reference": b["date_de_reference"], "answer": r["answer"],
                      "notes": r["notes"], "citations": r["citations"], "sources": srcs, "reponse_attendue": b["reponse_attendue"]})
    page = build_page("Évaluation humaine des réponses du système — schéma phase 4",
                      "Vous évaluez des réponses générées par le système local (Qwen) à partir des passages affichés. Pour chaque réponse : source, article, version juridique, réponse, citation, "
                      "justification et hallucination. Aucun score automatique n'est affiché.", "human_eval_p4", items, EVAL_JS)
    (OUT / "human_eval_p4.html").write_text(page, encoding="utf-8")
    print("écrit :", OUT / "human_eval_p4.html", f"({len(items)} réponses, échantillon de la phase 3)")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("review")
    s.add_argument("--corpus", default="D:/llm/snapshots/corpus_phase3_final")
    s = sp.add_parser("eval")
    s.add_argument("--runs", nargs="+", required=True)
    a = ap.parse_args()
    {"review": cmd_review, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
