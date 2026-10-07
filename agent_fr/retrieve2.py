"""Pipelines de recherche v2 (enregistrés dans agent_fr.pipelines) :

  bm25          BM25 pur (aucune règle juridique) — référence lexicale
  vector        multilingual-e5-small pur (cosinus) — référence sémantique
  hybrid_plain  fusion RRF BM25 + vecteurs, sans règle juridique — isole l'apport de la fusion
  hybrid        hybride + références (texte/article) + relations (abroge/modifie…) + logique TEMPORELLE (état actuel / version d'époque)
                + textes modificateurs + chaîne de versions + clarification des questions vagues
  hybrid_rerank hybride + reranker léger local (si installé)

Tout est local. L'ancien moteur (pipeline « legacy ») reste disponible (AGENT_RETRIEVER=legacy) comme repli.
"""
import calendar
import json
import os
import re
import time

import numpy as np

from . import embed
from .index import DOCS, Index
from .legal_status import load_legal
from .pipelines import PIPELINES
from .refs import parse_question
from boa_pipeline.relations import num_key
from .retrieve import Hit, Result, _coverage, _ref_terms, resolve_references
from .textproc import tokens

# ---- réglages (calibrés sur les jeux « dev » ; voir docs/RETRIEVAL_PHASE2.md) ---------------------------------------------------------
W_BM25, W_VEC, RRF_K = 1.0, 1.0, 60
RERANK_N, W_RERANK = int(os.environ.get("AGENT_RERANK_N", 20)), float(os.environ.get("AGENT_W_RERANK", 3.0))   # reranker : candidats réordonnés, poids du rang du reranker face au rang de la fusion (RRF)
TOPN = 60                    # candidats par moteur avant fusion
COS_MIN = 0.855              # cosinus minimal du meilleur passage (e5 : scores compressés ~0,75–0,92) ; dev : valides ≥ 0,861, hors-périmètre ≤ 0,853
COS_HIGH = 0.88              # au-dessus : correspondance « forte »
RR_MIN = float(os.environ.get("AGENT_RR_MIN", "-1.9"))   # seuil du meilleur score du reranker (cross-encoder, logit) : un passage dont le cosinus est juste sous COS_MIN mais que le
                             # reranker juge pertinent n'est pas refusé. Calibré sur le jeu dev seul (valides dev ≥ -1,43 ; hors-périmètre dev ≤ -2,31 → milieu -1,87)
MIN_COV = 0.30
MIN_RATIO = 0.12
SUPERSEDED_FACTOR = 0.92     # état actuel : texte abrogé/remplacé par un autre texte du corpus (simple départage : les scores RRF sont serrés)
FUTURE_FACTOR = 0.15         # version d'époque : texte postérieur à la date demandée
ABROGATED_FACTOR = 0.30      # version d'époque : texte déjà abrogé à la date demandée
VERSION_FACTOR = 0.60        # passage remplacé par une version plus récente de la même disposition (même famille de textes modificateurs)
AR = re.compile(r"[؀-ۿ]")

_STORE = {}


def is_arabic(q: str) -> bool:
    a = len(AR.findall(q))
    return a > 0 and a / max(1, len(re.findall(r"\w", q))) > 0.3


class VectorStore:
    """Vecteurs des chunks FR (alignés sur idx.chunks) puis AR (métadonnées chargées depuis chunks_ar.jsonl)."""

    def __init__(self, idx: Index):
        from .build_vectors import chunk_files, vectors_key
        langs = os.environ.get("AGENT_LANGS", "fr,ar").split(",")
        path = embed.vector_path(vectors_key(langs))
        if not path.exists():
            raise FileNotFoundError(f"vecteurs absents ({path}) : lancez  python -m agent_fr.build_vectors --langs {','.join(langs)}")
        self.V = np.load(path)
        meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self.n_fr = len(idx.chunks)
        assert meta["chunk_ids"][:self.n_fr] == [c["chunk_id"] for c in idx.chunks], "vecteurs désalignés avec l'index FR : reconstruisez-les"
        self.ar_chunks = []
        for lg, p in chunk_files(langs):
            if lg == "ar":
                self.ar_chunks = [json.loads(l) for l in open(p, encoding="utf-8")]
        assert len(self.ar_chunks) == len(self.V) - self.n_fr
        self.meta = meta

    def chunk(self, idx: Index, r: int) -> dict:
        return idx.chunks[r] if r < self.n_fr else self.ar_chunks[r - self.n_fr]

    def sims(self, qv, rows=None, arabic=False):
        """Cosinus (vecteurs normalisés) -> dict {ligne: score}. FR seul par défaut ; FR+AR pour une question arabe."""
        if rows is not None:
            r = np.fromiter(rows, dtype=np.int64)
            return dict(zip(r.tolist(), (self.V[r] @ qv).tolist()))
        end = len(self.V) if arabic else self.n_fr
        s = self.V[:end] @ qv
        top = np.argpartition(-s, min(TOPN, end - 1))[:TOPN]
        return {int(i): float(s[i]) for i in top}


def get_store(idx: Index) -> VectorStore:
    k = id(idx)
    if k not in _STORE:
        _STORE[k] = VectorStore(idx)
    return _STORE[k]


def _topn(sc: dict, n=TOPN):
    return sorted(sc, key=sc.get, reverse=True)[:n]


def rrf(lists_weights, k0=None):
    k0 = RRF_K if k0 is None else k0
    out = {}
    for ranking, w in lists_weights:
        for rank, i in enumerate(ranking, 1):
            out[i] = out.get(i, 0.0) + w / (k0 + rank)
    return out


# ------------------------------------------------------------------ temporel / juridique
MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
          "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
_MON = "|".join(MONTHS)
_PREP = r"(?:en|au|dans|durant|[àa] la fin de|fin|[àa] l['’]\s*[ée]poque de)"


def parse_as_of(question: str):
    """Date (fin de période, ISO) de la version historique demandée : « en 1998 » -> 1998-12-31, « en avril 1997 » -> 1997-04-30,
    « au 1er septembre 2016 » -> 2016-09-01, « avant 2018 » -> 2017-12-31. None si la question ne vise pas une époque."""
    q = question.lower()
    m = re.search(r"\bavant\s+(?:l['’]\s*(?:ann[ée]e\s+)?)?(19\d\d|20\d\d)", q)
    if m:
        return f"{int(m.group(1)) - 1}-12-31"
    m = re.search(_PREP + r"\s+(?:le\s+)?(\d{1,2}|1er)\s+(" + _MON + r")\s+(19\d\d|20\d\d)", q)
    if m:
        d = 1 if m.group(1) == "1er" else int(m.group(1))
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{d:02d}"
    m = re.search(_PREP + r"\s+(?:le\s+mois\s+d['’]\s*)?(" + _MON + r")\s+(19\d\d|20\d\d)", q)
    if m:
        y, mo = int(m.group(2)), MONTHS[m.group(1)]
        return f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
    m = re.search(_PREP + r"\s+(?:[\w’'éûè]+\s+){0,4}?(19[89]\d|20[0-3]\d)\b", q)
    if m:
        return f"{int(m.group(1))}-12-31"
    return None


MULTI_INTENT = re.compile(r"(?<!\w)(quels|quelles)\s+\w+(\s+\w+)?\s+(ont|a)(?!\w)|au cours de|tous les|toutes les|successiv|[ée]volu|historique", re.I)
CURRENT = re.compile(r"actuel|en vigueur|aujourd|d[ée]sormais|dernier|derni[èe]re|r[ée]cent|[àa] ce jour|applicable", re.I)
CHAIN_INTENT = re.compile(r"successiv|[ée]volu|historique|diff[ée]rentes? versions|au fil|avant et apr[èe]s|ancien(ne)? et nouve|\bpuis\b", re.I)


def year_of(date):
    return int(date[:4]) if date and date[:4].isdigit() else None


def _abrogators(doc: dict):
    return [e for key in ("abroge_par", "remplace_par") for e in doc.get(key, []) if not e.get("partial")]


SERIES_MATCH, SERIES_OTHER = 1.0, 0.4     # séries périodiques : les périodes AUTRES que celle demandée sont rétrogradées (jamais « abrogées ») ; la période demandée n'est pas boostée
                                         # (un boost ferait remonter les membres d'une série sans rapport avec la question : mesuré sur DEV, taux directeur 2022 -> note sur les taux excessifs 2022)


def get_legal():
    return load_legal(DOCS.parent / "legal_status.json")


def series_period_factor(legal, work_id: str, as_of, years, current: bool):
    """Séries périodiques (« fixé pour l'exercice 2012 ») : chaque texte vaut pour SA période ; on ne compare pas les dates de signature.
    Retourne None si le texte n'appartient pas à une série ; sinon un facteur selon la période visée par la question (année / date / « actuel »)."""
    sid, per = legal.member(work_id)
    if not sid:
        return None
    target = None
    if as_of is not None:
        y, m = int(as_of[:4]), int(as_of[5:7])
        target = (y, None if as_of.endswith("-12-31") else m)       # « en 2023 » = fin d'année = année entière (les deux semestres)
    elif len(years) == 1:
        target = (years[0], None)
    if target is not None:
        y, m = target
        if per["sorte"] == "semestre":
            v = y + (0.5 if (m and m > 6) else 0.0)
            ok = (per["debut"] <= v <= per["fin"]) if m else int(per["debut"]) == y
        else:
            ok = per["debut"] <= y <= per["fin"]
        return SERIES_MATCH if ok else SERIES_OTHER
    if current:
        return SERIES_MATCH if per["fin"] == legal.series_latest(sid) else SERIES_OTHER
    return 1.0


def series_notes(legal, hits, as_of, years, current) -> list:
    """Notes pour l'utilisateur sur les séries périodiques présentes parmi les passages : période visée absente, ou dernière période publiée."""
    out, seen = [], set()
    for h in hits[:6]:
        sid, per = legal.member(h.chunk["work_id"])
        if not sid or sid in seen:
            continue
        seen.add(sid)
        ser = legal.series[sid]
        if as_of is not None or len(years) == 1:
            matched = any(series_period_factor(legal, m["work_id"], as_of, years, False) == SERIES_MATCH for m in ser["membres"])
            if not matched:
                out.append(f"Série périodique : aucun texte du corpus ne vise la période demandée ; périodes disponibles de {ser['membres'][0]['debut']:g} à {ser['derniere_periode']:g}. "
                           "Les textes retrouvés valent pour d'AUTRES périodes : ne pas les présenter comme la valeur demandée.")
        elif current:
            out.append(f"Série périodique : dernière période publiée dans le corpus = {ser['derniere_periode']:g} ; une période plus récente peut exister hors corpus. "
                       "Les périodes antérieures ne sont pas abrogées, elles valent pour leur période.")
    return out


def temporal_factor(idx: Index, chunk: dict, as_of, years=(), current=False):
    doc = idx.docs.get(chunk["document_id"])
    if doc is None:
        return 1.0
    legal = get_legal()
    if legal.available:
        f = series_period_factor(legal, chunk["work_id"], as_of, years, current)
        if f is not None:
            return f
    if as_of is not None:
        d = chunk.get("date") or ""
        if d and d > as_of:
            return FUTURE_FACTOR
        for e in _abrogators(doc):
            ed = e.get("date") or ""
            if ed and ed <= as_of:
                return ABROGATED_FACTOR
        return 1.0
    if year_of(chunk.get("date")) in years:
        return 1.0                                           # l'année citée désigne ce texte : on ne le rétrograde pas
    return SUPERSEDED_FACTOR if _abrogators(doc) else 1.0


_TARGET_RE = re.compile(r"article\s+(\d+(?:\s*(?:bis|ter|quater))?)\s+(?:du|de l['’]\s*|de la\s+)?\s*"
                        r"(?:r[èe]glement|instruction|loi|ordonnance|d[ée]cret|note)\s+n\s*[°º]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4})", re.I)
_TARGETS = {}
PAIR_COS_WHOLE = 0.95        # remplacement d'un texte entier : le passage homologue doit être quasi identique par le sujet


def _art_norm(a) -> str:
    return re.sub(r"\s+", " ", str(a).strip().lower())


def amended_targets(chunk: dict) -> set:
    """Couples (clé du numéro, article) que le passage déclare expressément modifier : « L'article 3 de l'instruction n° 02-2004 est modifié »."""
    cid = chunk["chunk_id"]
    if cid not in _TARGETS:
        out = set()
        for m in _TARGET_RE.finditer(chunk.get("text", "")):
            num = re.sub(r"\s+", "", m.group(2).replace("–", "-").replace("/", "-"))
            out.add((num_key(num), _art_norm(m.group(1))))
        _TARGETS[cid] = out
    return _TARGETS[cid]


def identity(chunk: dict):
    if chunk.get("number") and chunk.get("article"):
        return (num_key(chunk["number"]), _art_norm(chunk["article"]))
    return None


def explicitly_amends(b: dict, a: dict) -> bool:
    ident = identity(a)
    return bool(ident) and ident in amended_targets(b)


def _whole_text_replaces(idx, b: dict, a: dict) -> bool:
    docb, doca = idx.docs.get(b["document_id"]), idx.docs.get(a["document_id"])
    if not docb or not doca:
        return False
    return any(e.get("work_id") == doca["work_id"] and not e.get("partial") for k in ("abroge", "remplace") for e in docb.get(k, []))


def supersedes(idx, store, hb, ha) -> bool:
    """Le passage hb est-il une version plus récente de la disposition du passage ha ? Preuve TEXTUELLE (article visé) ou remplacement de texte entier."""
    b, a = hb.chunk, ha.chunk
    if not b.get("date") or not a.get("date") or b["date"] <= a["date"]:
        return False
    if explicitly_amends(b, a):
        return True
    tb, ta = amended_targets(b), amended_targets(a)
    if tb and ta and tb & ta:                                   # deux modifications du même article : la plus récente l'emporte
        return True
    return (_whole_text_replaces(idx, b, a) and getattr(hb, "row", None) is not None and getattr(ha, "row", None) is not None
            and float(store.V[hb.row] @ store.V[ha.row]) >= PAIR_COS_WHOLE)


def add_modifiers(idx, store, qv, hits, as_of, max_extra=3):
    """Remonte, juste AU-DESSUS du passage d'origine, le passage des textes qui le modifient expressément (article visé) ou le remplacent."""
    out, have = [], {(h.chunk["work_id"], h.chunk.get("article")) for h in hits}
    extra = {}
    for h in hits[:4]:
        doc = idx.docs.get(h.chunk["document_id"])
        if not doc or h.chunk.get("language") == "ar":
            continue
        for key, verb in (("modifie_par", "modifie"), ("complete_par", "complète"), ("abroge_par", "abroge"), ("remplace_par", "remplace")):
            for e in doc.get(key, []):
                did = e.get("document_id")
                if not did or e["work_id"] == h.chunk["work_id"] or did not in idx.by_doc:
                    continue
                if as_of is not None and (e.get("date") or "") > as_of:
                    continue                      # modification postérieure à la date demandée
                rows = idx.by_doc[did]
                cand = [r for r in rows if explicitly_amends(idx.chunks[r], h.chunk)]
                if not cand and key in ("abroge_par", "remplace_par") and getattr(h, "row", None) is not None:
                    pair = store.V[rows] @ store.V[h.row]
                    j = int(np.argmax(pair))
                    if float(pair[j]) >= PAIR_COS_WHOLE:
                        cand = [rows[j]]
                if not cand:
                    continue
                r = max(cand, key=lambda r: float(store.V[r] @ qv))
                c = idx.chunks[r]
                if (c["work_id"], c.get("article")) in have:
                    continue
                have.add((c["work_id"], c.get("article")))
                m = Hit(c, h.score * 1.02, 0.0, via=f"{verb} le texte « {h.chunk['document_type']} n° {h.chunk['number']} » cité plus bas")
                m.row, m.cos = r, float(store.V[r] @ qv)
                extra.setdefault(id(h), []).append(m)
    for h in hits:
        for m in sorted(extra.get(id(h), []), key=lambda x: x.chunk.get("date") or "", reverse=True)[:max_extra]:
            out.append(m)
        out.append(h)
    return out


def expand_chain(idx, store, qv, hits, question, parsed, max_extra=5):
    """Questions « quels textes ont successivement… » ou deux dates (« en 1995 puis en 1996 ») : ajoute le meilleur passage de chaque texte
    de la chaîne de versions (modifie / abroge / complète / remplace, dans les deux sens) des meilleurs résultats."""
    if not (CHAIN_INTENT.search(question) or len(set(parsed["years"])) >= 2):
        return hits
    have = {(h.chunk["work_id"], h.chunk.get("article")) for h in hits}
    by_work = {}
    for d in idx.docs.values():
        by_work.setdefault(d["work_id"], d)
    seeds = [h.chunk["document_id"] for h in hits[:2]]
    seen_docs, frontier = set(), list(seeds)
    for _ in range(2):                                      # 2 niveaux de profondeur dans la chaîne
        nxt = []
        for did in frontier:
            doc = idx.docs.get(did)
            if not doc or did in seen_docs:
                continue
            seen_docs.add(did)
            for key in ("modifie_par", "complete_par", "abroge_par", "remplace_par", "modifie", "complete", "abroge", "remplace"):
                for e in doc.get(key, []):
                    other = idx.docs.get(e.get("document_id")) if e.get("document_id") else by_work.get(e.get("work_id"))
                    if other and other["document_id"] in idx.by_doc and other["document_id"] not in seen_docs:
                        nxt.append(other["document_id"])
        frontier = nxt
    extra = []
    for did in (seen_docs | set(frontier)) - set(seeds):
        if did not in idx.by_doc:
            continue
        sims = store.sims(qv, idx.by_doc[did])
        r, s_ = max(sims.items(), key=lambda kv: kv[1])
        c = idx.chunks[r]
        if (c["work_id"], c.get("article")) in have:
            continue
        have.add((c["work_id"], c.get("article")))
        m = Hit(c, 0.0, 0.0, via="appartient à la même chaîne de versions (modification / abrogation / remplacement) que les résultats précédents")
        m.row, m.cos = r, s_
        extra.append(m)
    extra.sort(key=lambda x: -x.cos)
    floor = hits[-1].score * 0.99 if hits else 0.0
    for m in extra[:max_extra]:
        m.score = floor
    return hits + extra[:max_extra]


def resolve_versions(idx, store, hits, as_of, years=()):
    """Si un passage a été remplacé par une version plus récente de la MÊME disposition (preuve textuelle, voir supersedes), il est rétrogradé ;
    la version la plus récente applicable (≤ as_of s'il est fourni) garde son score. Un texte dont l'année est citée dans la question n'est jamais rétrogradé."""
    cand = [h for h in hits if h.chunk.get("language") != "ar" and h.chunk.get("date")]
    for a in cand:
        if year_of(a.chunk["date"]) in years:
            continue
        for b in cand:
            if a is b or (as_of is not None and b.chunk["date"] > as_of):
                continue
            if supersedes(idx, store, b, a):
                a.score *= VERSION_FACTOR
                a.superseded_by = b.chunk["chunk_id"]
                break
    return sorted(hits, key=lambda h: -h.score)


_ATTRIBUTE_WORDS = ("taux montant plafond seuil délai durée condition conditions sanction sanctions obligation obligations procédure date nombre "
                    "pourcentage limite minimum maximum règle règles disposition dispositions texte article commission commissions frais tarif "
                    "modalité modalités formalité formalités exigence exigences mesure mesures valeur chiffre prix coût cout "
                    # qualificatifs sans sujet (« le délai applicable », « le taux en vigueur ») : ajoutés après la mesure v5 (voir docs/RETRIEVAL_PHASE2.md)
                    "applicable applicables vigueur actuel actuelle actuels prévu prévue prévus prévues requis requise exigé exigée fixé fixée autorisé autorisée "
                    # renvois sans référent (« le texte est-il encore applicable ? », « différence entre l'ancien et le nouveau régime ? ») : ajoutés après la mesure DEV du benchmark phase 3
                    "encore ancien ancienne anciens nouveau nouvelle nouveaux régime différence")
GENERIC_STEMS = {t for w in _ATTRIBUTE_WORDS.split() for t in tokens(w)}


_INVERSION = re.compile(r"^(est|sont|peut|peuvent|doit|doivent|a|ont|faut|y|va|vont)-(t-)?(il|elle|ils|elles|on)s?$")      # « est-il », « peut-on » : mots vides


def is_vague(idx: Index, question: str, parsed: dict):
    """Question sans sujet : « article N » sans texte, ou tous les termes porteurs sont des mots d'attribut (« Quel est le taux ? »)."""
    toks = list(dict.fromkeys(t for t in tokens(question) if t not in _ref_terms(parsed) and not t.isdigit() and not _INVERSION.match(t)))
    if parsed["articles"] and not parsed["refs"] and not toks:
        return "article_sans_texte"
    if parsed["refs"]:
        return None
    if toks and all(t in GENERIC_STEMS for t in toks):
        return "termes_generiques"
    return None


# ------------------------------------------------------------------ pipeline
def _make_hits(idx, store, fused, bm25, vec, content, k):
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])
    hits, seen = [], {}
    for r, s in ranked:
        c = store.chunk(idx, r)
        key = (c["work_id"], c.get("article"), c["unit_kind"], c.get("part"), c.get("language"))
        if key in seen:
            seen[key].other_copies.append(c["document_id"])
            continue
        cov = _coverage(idx, content, r) if (r < store.n_fr and content) else 0.0
        up = sum(idx.idf.get(t, idx.max_idf) * 2.4 for t in set(content)) or 1.0
        h = Hit(c, s, cov, ratio=(bm25.get(r, 0.0) / up))
        h.row, h.cos = r, vec.get(r, 0.0)
        seen[key] = h
        hits.append(h)
        if len(hits) >= k:
            break
    return hits


def search_v2(idx: Index, question: str, k: int = 6, mode: str = "hybrid") -> Result:
    t_all = time.perf_counter()
    store = get_store(idx)
    parsed = parse_question(question)
    notes: list[str] = []
    q_all = tokens(question)
    arabic = is_arabic(question)
    full = mode in ("hybrid", "hybrid_rerank")
    restrict = None
    if full:
        restrict, early = resolve_references(idx, question, parsed, notes)
        if early is not None:
            return early
    content = [t for t in q_all if t not in _ref_terms(parsed)] if restrict is not None else q_all
    score_terms = list(content if content else q_all)
    if full and re.search(r"d[ée]fini|d[ée]finition|qu.est[- ]ce|signifie|d[ée]signe|entend", question, re.I):
        score_terms += ["entend", "entend", "defin"]

    timings = {}
    t0 = time.perf_counter()
    qv = embed.get_embedder().embed_query(question) if mode != "bm25" else None
    timings["embed_question_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    t0 = time.perf_counter()
    bm = idx.scores(score_terms, restrict) if (mode != "vector" and not arabic) else {}
    vec = store.sims(qv, restrict, arabic) if qv is not None else {}
    if restrict is not None and not vec and not bm:
        bm = {i: 1.0 - n * 1e-3 for n, i in enumerate(sorted(restrict)[:k * 2])}
    if mode == "bm25":
        fused = dict(bm)
    elif mode == "vector":
        fused = dict(vec)
    else:
        fused = rrf([(_topn(bm), W_BM25), (_topn(vec), W_VEC)])
    timings["search_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    as_of = parse_as_of(question) if (full and len(set(parsed["years"])) < 2) else None   # « en 1995 puis en 1996 » : chaîne de versions, pas une date
    cur_intent = bool(CURRENT.search(question)) if full else False
    if mode == "hybrid_rerank" and restrict is None and get_legal().available:     # séries périodiques : une première fois AVANT le choix des candidats du reranker (sinon la bonne
        # période peut ne pas y entrer), puis de nouveau sur les scores finaux (le mélange par rangs du reranker efface les écarts de score)
        legal0 = get_legal()
        for r in list(fused):
            c0 = store.chunk(idx, r)
            if c0.get("language") != "ar":
                f0 = series_period_factor(legal0, c0["work_id"], as_of, tuple(parsed["years"]), cur_intent)
                if f0 is not None:
                    fused[r] *= f0
    rr_best = None
    if mode == "hybrid_rerank" and len(fused) > 1:
        from .rerank import get_reranker
        t0 = time.perf_counter()
        cand = sorted(fused, key=fused.get, reverse=True)[:RERANK_N]
        rr = get_reranker().score(question, [store.chunk(idx, r)["text_with_context"] for r in cand])
        rr_best = max(rr)
        rank_r = {r: n for n, r in enumerate(sorted(range(len(cand)), key=lambda j: -rr[j]), 1)}
        fused = {r: 1.0 / (RRF_K + n) + W_RERANK / (RRF_K + rank_r[n - 1]) for n, r in enumerate(cand, 1)}
        for n, r in enumerate(cand):
            vec.setdefault(r, float(store.V[r] @ qv))
        timings["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        timings["rerank_best"] = round(rr_best, 2)

    if full and restrict is None:
        for r in list(fused):
            c = store.chunk(idx, r)
            if c.get("language") != "ar":
                fused[r] *= temporal_factor(idx, c, as_of, tuple(parsed["years"]), cur_intent)
        if parsed["years"] and as_of is None:
            legal = get_legal()
            for r in list(fused):
                c = store.chunk(idx, r)
                y = year_of(c.get("date"))
                if y and y in parsed["years"] and not legal.member(c["work_id"])[0]:
                    fused[r] *= 1.25
    hits = _make_hits(idx, store, fused, bm, vec, content, k)
    if not hits:
        return Result(question, False, "aucun_passage_pertinent", [], parsed, notes, timings=timings)
    if full and restrict is None and qv is not None and not arabic:
        hits = add_modifiers(idx, store, qv, hits, as_of)
        hits = expand_chain(idx, store, qv, hits, question, parsed)
        if not MULTI_INTENT.search(question) and len(set(parsed["years"])) < 2:
            hits = resolve_versions(idx, store, hits, as_of, tuple(parsed["years"]))
    if full and cur_intent:
        notes.append("Le corpus ne permet pas d'établir quel texte est actuellement en vigueur (le site ne publie pas de statut de vigueur) : "
                     "les textes les plus récents sont privilégiés, à vérifier auprès de la Banque d'Algérie.")
    if full and restrict is None and get_legal().available:
        notes.extend(series_notes(get_legal(), hits, as_of, tuple(parsed["years"]), cur_intent))
    if as_of is not None:
        notes.append(f"Version recherchée : état de la réglementation au {as_of} (textes postérieurs écartés ou rétrogradés).")
    timings["total_ms"] = round((time.perf_counter() - t_all) * 1000, 1)

    if full and restrict is None:
        why = is_vague(idx, question, parsed)
        if why:
            titles = []
            for h in hits[:6]:
                t = f"{h.chunk['document_type'].capitalize()} n° {h.chunk['number']}"
                if t not in titles:
                    titles.append(t)
            return Result(question, False, "question_ambigue", hits[:5], parsed,
                          [f"Votre question est trop générale. Précisez le sujet, le texte (numéro) ou la période. Textes possibles : {'; '.join(titles[:5])}."],
                          clarify=True, timings=timings)
    best = max(hits, key=lambda h: getattr(h, "cos", 0.0)) if vec else hits[0]
    cos = getattr(best, "cos", 0.0)
    if restrict is None:
        ok = (best.coverage >= MIN_COV and best.ratio >= MIN_RATIO) if mode == "bm25" else (cos >= COS_MIN or (rr_best is not None and rr_best >= RR_MIN))
        if not ok:
            return Result(question, False, "aucun_passage_pertinent", hits[:3], parsed, notes, timings=timings)
        conf = "forte" if (mode == "bm25" or cos >= COS_HIGH) else "partielle"
        if conf == "partielle":
            notes.append("Correspondance partielle : vérifiez que ces passages répondent bien à votre question.")
        return Result(question, True, "ok", hits, parsed, notes, conf, timings=timings)
    return Result(question, True, "ok", hits, parsed, notes, "forte", timings=timings)


def _register(name):
    PIPELINES[name] = lambda idx, q, k=6, _m=name: search_v2(idx, q, k, _m)


for _n in ("bm25", "vector", "hybrid_plain", "hybrid", "hybrid_rerank"):
    _register(_n)
