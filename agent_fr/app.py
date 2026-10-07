"""Interface web locale (127.0.0.1 uniquement). Les textes du corpus sont insérés via textContent (jamais innerHTML)."""
import os

from flask import Flask, jsonify, request

from .agent import ask, get_index

app = Flask(__name__)

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RegAssist DZ — assistant réglementaire (français)</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#6b6560;--card:#fff;--bd:#e7e5e4;--acc:#14532d;--warn:#92400e;--warnbg:#fef3c7}
@media (prefers-color-scheme:dark){:root{--bg:#161412;--fg:#f5f5f4;--mut:#a8a29e;--card:#201d1a;--bd:#3a3531;--acc:#86efac;--warn:#fcd34d;--warnbg:#3a2e0a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 80px}h1{font-size:1.4rem;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 20px}
form{display:flex;gap:8px;flex-wrap:wrap}input[type=text]{flex:1 1 320px;padding:12px 14px;border:1px solid var(--bd);border-radius:10px;background:var(--card);color:var(--fg);font:inherit}
button{padding:12px 18px;border:0;border-radius:10px;background:var(--acc);color:var(--bg);font:inherit;font-weight:600;cursor:pointer}button:disabled{opacity:.5}
label{display:flex;align-items:center;gap:6px;color:var(--mut);font-size:.9rem;margin-top:8px}
.ans{margin-top:22px;white-space:pre-wrap}.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px 16px;margin:14px 0}
.card h3{margin:0 0 4px;font-size:1rem}.meta{color:var(--mut);font-size:.88rem}.q{margin:10px 0;padding-left:12px;border-left:3px solid var(--bd);white-space:pre-wrap}
.tag{display:inline-block;background:var(--warnbg);color:var(--warn);border-radius:6px;padding:1px 8px;font-size:.8rem;margin:2px 4px 2px 0}
.refuse{background:var(--warnbg);color:var(--warn);padding:12px 14px;border-radius:10px}.disc{margin-top:26px;color:var(--mut);font-size:.85rem}
a{color:var(--acc)}.sec{font-size:1.1rem;margin:24px 0 4px;border-bottom:1px solid var(--bd);padding-bottom:4px}</style></head><body><main>
<h1>RegAssist DZ</h1><p class="sub">Textes réglementaires de la Banque d'Algérie (français) — réponses citées, jamais inventées.</p>
<form id="f"><input type="text" id="q" placeholder="Ex. : Que dit l'article 5 du règlement n° 14-02 ?" autofocus required>
<button id="b">Rechercher</button></form>
<label><input type="checkbox" id="llm"> Rédiger la réponse avec le LLM local (Qwen, sur cette machine ; aucune donnée ne quitte l'ordinateur)</label>
<div id="out"></div></main>
<script>
const out=document.getElementById('out');
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x!==undefined)e.textContent=x;return e}
function sourceCard(c,cited){
  const card=el('div','card');
  const pg='p. '+c.page+((c.page_fin&&c.page_fin!==c.page)?'–'+c.page_fin:'')+' du PDF';
  card.append(el('h3','',`[${c.id}] ${c.texte}`));
  const path=[c.chapitre,c.section].filter(Boolean).join(' > ');if(path)card.append(el('div','meta',path));
  card.append(el('div','q',c.extrait));
  const m=el('div','meta');
  m.append(el('span','tag','Document : '+c.texte));
  m.append(el('span','tag','Article : '+(c.emplacement||'passage')+' ('+pg+')'));
  if(c.date)m.append(el('span','tag','Date : '+c.date));
  m.append(el('span','tag','Statut : '+c.statut));
  if(c.statut_juridique)m.append(el('span','tag','Statut juridique : '+c.statut_juridique+' (confiance '+c.statut_confiance+')'));
  if(c.score!==undefined)m.append(el('span','tag','Score : '+c.score+(c.similarite?' (similarité sémantique '+c.similarite+')':'')));
  if(cited)m.append(el('span','tag','Cité dans la réponse'));
  if(c.a_verifier)m.append(el('span','tag','Document à vérifier (contrôle humain)'));
  if(c.extraction==='ocr'||c.extraction==='mixed')m.append(el('span','tag','Texte issu de l’OCR'));
  if(c.ocr_uncertain)m.append(el('span','tag','OCR_UNCERTAIN : valeur numérique non corroborée'));
  card.append(m);
  if(c.statut_detail)card.append(el('div','meta','Statut juridique : '+c.statut_detail));
  if(c.via)card.append(el('div','meta','↳ Texte qui '+c.via));
  if(c.alerte)card.append(el('div','refuse',c.alerte));
  Object.entries(c.relations||{}).forEach(([k,v])=>card.append(el('div','meta',k+' : '+v.join(' ; '))));
  const l=el('div','meta');l.append(document.createTextNode('Source : '));
  [['PDF officiel',c.document_url],['Page du site',c.source_url]].forEach(([n,u],i)=>{
    if(i)l.append(document.createTextNode(' · '));const a=el('a','',n);a.href=u;a.target='_blank';a.rel='noopener noreferrer';l.append(a)});
  card.append(l);return card;
}
// d = réponse de l'agent. Deux blocs distincts : « Sources retrouvées » (recherche locale, texte du corpus tel quel) PUIS « Réponse générée »
// (rédigée par le LLM local uniquement à partir de ces sources). pending = rédaction LLM en cours : on n'affiche que les sources.
function render(d,status,pending){
  const box=document.createElement('div');
  if(status)box.append(el('p','meta',status));
  const srcs=d.sources||d.citations||[], cited=new Set((d.citations||[]).map(c=>c.id)), gen=d.mode==='llm';
  if(srcs.length){
    box.append(el('h2','sec','Sources retrouvées ('+srcs.length+')'));
    const t=d.timings||{};
    box.append(el('p','meta','Recherche locale'+(d.retriever?' ('+d.retriever+')':'')+(t.total_ms!==undefined?' : '+Math.round(t.total_ms)+' ms':'')+'. Extraits du corpus reproduits tels quels.'));
    srcs.forEach(c=>box.append(sourceCard(c,gen&&d.found&&cited.has(c.id))));
  }
  if(!pending){
    if(d.clarify)box.append(el('h2','sec','Précision nécessaire'));
    else box.append(el('h2','sec',gen?'Réponse générée':'Réponse'));
    if(gen&&d.found)box.append(el('p','meta','Rédigée par '+(d.model||'le LLM')+(d.latency_s?' en '+d.latency_s+' s':'')+', strictement à partir des sources ci-dessus ; vérifiez les citations.'));
    if(d.found&&!d.clarify&&!gen)box.append(el('p','meta','Mode extractif : aucun texte généré, les sources ci-dessus sont la réponse.'));
    else box.append(el('div',(d.found&&!d.clarify)?'ans':'refuse',d.answer));
  }
  (d.notes||[]).forEach(n=>box.append(el('p','meta','Note : '+n)));
  box.append(el('p','disc',d.disclaimer));
  out.replaceChildren(box);
}
async function ask(q,llm){
  const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,llm:llm})});
  return await r.json();
}
document.getElementById('f').addEventListener('submit',async ev=>{
  ev.preventDefault();const b=document.getElementById('b');b.disabled=true;
  const q=document.getElementById('q').value,wantLlm=document.getElementById('llm').checked;
  out.replaceChildren(el('p','meta','Recherche…'));
  try{
    const d0=await ask(q,false);                       // passages affichés tout de suite (instantané)
    render(d0,wantLlm&&d0.found?'Passages trouvés — rédaction par le LLM en cours (20 à 60 s sur CPU)…':'',wantLlm&&d0.found);
    if(wantLlm&&d0.found){const d1=await ask(q,true);render(d1,'');}
  }catch(e){out.replaceChildren(el('p','refuse','Erreur : '+e))}
  b.disabled=false;});
</script></body></html>"""


@app.get("/")
def home():
    return PAGE


@app.post("/api/ask")
def api_ask():
    data = request.get_json(force=True, silent=True) or {}
    q = str(data.get("question", ""))[:500]
    return jsonify(ask(q, use_llm=bool(data.get("llm"))))


def run():
    get_index()
    port = int(os.environ.get("AGENT_PORT", "8765"))
    print(f"RegAssist DZ : http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
