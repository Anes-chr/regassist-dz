"""Recherche : références explicites (texte / article) d'abord, sinon BM25 ; décision de refus fondée sur la couverture."""
from dataclasses import dataclass, field

from boa_pipeline.classify import TYPE_LABEL

from .index import Index
from .refs import parse_question
from .textproc import tokens

import re

# Seuils calibrés sur 11 questions de fond (ratio 0,42–0,95 ; couverture 0,69–1,0) et 9 hors sujet (cf. agent_fr/eval).
# Un filtre lexical ne distingue pas les questions hors sujet qui reprennent des mots du corpus : voir `confidence`.
MIN_COVERAGE = 0.30    # en dessous : refus (les questions valides et hors sujet se recouvrent lexicalement : compromis assumé)
MIN_RATIO = 0.16       # idem, score BM25 rapporté au maximum théorique de la question
PRF_WEIGHT = 0.0       # expansion de requête (pseudo-retour de pertinence) : TESTÉE, dégrade le rang 1 sur le jeu dev → désactivée
REL_VERBS = [("abroge", r"abrog"), ("modifie", r"modifi"), ("complete", r"compl[eè]t|ajout"), ("remplace", r"remplac|substitu")]


@dataclass
class Hit:
    chunk: dict
    score: float
    coverage: float
    ratio: float = 0.0
    other_copies: list = field(default_factory=list)
    via: str = ""          # « modifie / abroge / complète le texte du passage précédent » (texte modificateur remonté)
    superseded_by: str = ""    # chunk_id d'une version plus récente de la même disposition (preuve textuelle) : ce passage n'est plus donné au LLM


@dataclass
class Result:
    question: str
    found: bool
    reason: str            # ok | texte_cite_introuvable | aucun_passage_pertinent | article_introuvable
    hits: list
    parsed: dict
    notes: list = field(default_factory=list)
    confidence: str = ""     # forte | partielle (à confirmer par l'utilisateur)
    clarify: bool = False    # question trop vague : l'agent demande une précision (nouveaux pipelines)
    timings: dict = field(default_factory=dict)   # ms : embedding de la question, fusion, reranking…


def _coverage(idx: Index, terms: list[str], i: int) -> float:
    if not terms:
        return 1.0
    tot = got = 0.0
    for t in set(terms):
        w = idx.idf.get(t, idx.max_idf)
        tot += w
        if t in idx.tf[i]:
            got += w
    return got / tot if tot else 0.0


def _ref_terms(parsed: dict) -> set[str]:
    out = set()
    for r in parsed["refs"]:
        out.update(tokens(r["number"]))
    for a in parsed["articles"]:
        out.update(tokens(a))
    return out | {"articl", "reglement", "instruct", "loi", "ordonnanc", "note", "lign", "directric", "n", "dit", "prevoit", "prevoi"}


def _add_modifiers(idx: Index, question: str, hits: list, content: list, max_extra: int = 3) -> list:
    """Si un passage appartient à un texte modifié / complété / abrogé / remplacé par un autre texte du corpus, on remonte le meilleur
    passage du texte modificateur : l'utilisateur voit la version la plus récente, pas seulement la plus proche de sa question."""
    have = {(h.chunk["work_id"], h.chunk.get("article")) for h in hits}
    extra = []
    for h in hits[:3]:
        doc = idx.docs.get(h.chunk["document_id"])
        if not doc:
            continue
        for key, verb in (("modifie_par", "modifie"), ("complete_par", "complète"), ("abroge_par", "abroge"), ("remplace_par", "remplace")):
            for e in doc.get(key, []):
                did = e.get("document_id")
                if not did or e["work_id"] == h.chunk["work_id"]:
                    continue
                rest = set(idx.by_doc.get(did, []))
                sc = idx.scores(content, rest)
                if not sc:
                    continue
                i, s_ = max(sc.items(), key=lambda kv: kv[1])
                c = idx.chunks[i]
                if (c["work_id"], c.get("article")) in have:
                    continue
                have.add((c["work_id"], c.get("article")))
                extra.append(Hit(c, s_, _coverage(idx, content, i), via=f"{verb} le texte « {h.chunk['document_type']} n° {h.chunk['number']} » cité plus haut"))
    extra.sort(key=lambda x: (x.chunk.get("date") or ""), reverse=True)
    return hits + extra[:max_extra]


def resolve_references(idx: Index, question: str, parsed: dict, notes: list):
    """Résout « règlement n° X », « article N » et les relations (« quelle instruction abroge… ») : retourne (restrict, early).
    restrict : ensemble d'indices de chunks autorisés (ou None) ; early : Result de refus précis (texte/article introuvable) ou None.
    Factorisé pour que tous les pipelines (legacy, hybride…) appliquent exactement la même logique de références."""
    restrict = None
    if parsed["refs"]:
        found_idx: set[int] = set()
        for r in parsed["refs"]:
            labels = [TYPE_LABEL[r["type_code"]]] if r["type_code"] else list(set(TYPE_LABEL.values()))
            for lb in labels:
                found_idx.update(idx.by_ref.get((lb, r["key"]), []))
        if not found_idx:
            return None, Result(question, False, "texte_cite_introuvable", [], parsed,
                          ["Le texte cité n'existe pas dans le corpus collecté (il peut exister sur le site mais ne pas avoir été collecté)."])
        restrict = found_idx
        rel = next((key for key, pat in REL_VERBS if re.search(pat, question, re.I)), None)
        rel_applied = False
        if rel:
            # « quelle instruction abroge l'instruction n° X ? » : on cherche les textes QUI citent X avec ce verbe
            targets = {idx.chunks[i]["work_id"] for i in found_idx}
            rel_docs = [d["document_id"] for d in idx.docs.values()
                        if any(e.get("work_id") in targets for e in d.get(rel, [])) and d["work_id"] not in targets]
            rel_idx = {i for did in rel_docs for i in idx.by_doc.get(did, [])}
            if rel_idx:
                restrict = rel_idx
                rel_applied = True
                notes.append("Textes du corpus dont l'intitulé ou le contenu indique qu'ils "
                             + {"abroge": "abrogent", "modifie": "modifient", "complete": "complètent", "remplace": "remplacent"}[rel]
                             + " le texte cité (relation détectée automatiquement : à vérifier dans le document).")
        if parsed["articles"] and not rel_applied:   # « article 2 de l'instruction X » désigne un article du texte X, pas du texte modificateur
            art = {i for i in restrict if idx.chunks[i].get("article") in parsed["articles"]}
            if art:
                restrict = art
            else:
                have = sorted({idx.chunks[i].get("article") for i in found_idx if idx.chunks[i].get("article")},
                              key=lambda a: (len(a), a))
                first = idx.chunks[sorted(found_idx)[0]]
                return None, Result(question, False, "article_introuvable", [], parsed,
                              [f"L'article {', '.join(parsed['articles'])} n'existe pas dans « {first['document_type']} n° {first['number']} » "
                               f"tel que collecté (articles trouvés : {', '.join(have[:40]) or 'aucun'})."])
    return restrict, None


def search(idx: Index, question: str, k: int = 6) -> Result:
    parsed = parse_question(question)
    q_all = tokens(question)
    notes: list[str] = []
    restrict, early = resolve_references(idx, question, parsed, notes)
    if early is not None:
        return early

    content = [t for t in q_all if t not in _ref_terms(parsed)] if restrict is not None else q_all
    score_terms = list(content if content else q_all)
    if re.search(r"d[ée]fini|d[ée]finition|qu.est[- ]ce|signifie|d[ée]signe|entend", question, re.I):
        score_terms += ["entend", "entend", "defin"]   # question de définition : les articles « on entend par… » sont favorisés
    sc = idx.scores(score_terms, restrict)
    if PRF_WEIGHT and sc and restrict is None:
        first = [i for i, _ in sorted(sc.items(), key=lambda kv: -kv[1])]
        exp = {t: PRF_WEIGHT * v for t, v in idx.expansion_terms(first, score_terms).items()}
        if exp:
            sc = idx.scores(score_terms, restrict, extra=exp)

    if restrict is not None and not sc:
        order = sorted(restrict)[:k * 2]            # question « que dit le règlement X ? » : on rend le texte dans l'ordre
        sc = {i: 1.0 for i in order}
        pos = {i: n for n, i in enumerate(order)}
        for i in order:
            sc[i] = 1.0 - pos[i] * 1e-3
    if parsed["years"]:
        for i in list(sc):
            y = (idx.chunks[i].get("date") or "")[:4]
            if y and int(y) in parsed["years"]:
                sc[i] *= 1.25

    temporal = bool(re.search(r"actuel|en vigueur|aujourd|d[ée]sormais|dernier|derni[èe]re|r[ée]cent|[àa] ce jour|toujours|applicable", question, re.I))
    ranked = sorted(sc.items(), key=lambda kv: -kv[1])
    hits, seen = [], {}
    for i, s in ranked:
        c = idx.chunks[i]
        key = (c["work_id"], c.get("article"), c["unit_kind"], c.get("part"))
        if key in seen:
            seen[key].other_copies.append(c["document_id"])
            continue
        up = sum(idx.idf.get(t, idx.max_idf) * 2.4 for t in set(content or q_all)) or 1.0
        h = Hit(c, s, _coverage(idx, content or q_all, i), ratio=s / up)
        seen[key] = h
        hits.append(h)
        if len(hits) >= k:
            break

    if not hits:
        return Result(question, False, "aucun_passage_pertinent", [], parsed, notes)
    if temporal:
        notes.append("Le corpus ne permet pas d'établir quel texte est actuellement en vigueur (le site ne publie pas de statut de "
                     "vigueur) : les passages sont classés du plus récent au plus ancien, à vérifier auprès de la Banque d'Algérie.")
        top = hits[0].score
        hits.sort(key=lambda h: (-(h.score >= 0.7 * top), h.chunk.get("date") or ""), reverse=False)
        hits = sorted(hits, key=lambda h: (h.score >= 0.7 * top, h.chunk.get("date") or ""), reverse=True)
    hits = _add_modifiers(idx, question, hits, content or q_all)
    if restrict is None:
        best = hits[0] if not temporal else max(hits, key=lambda h: h.ratio)
        if best.coverage < MIN_COVERAGE or best.ratio < MIN_RATIO:
            return Result(question, False, "aucun_passage_pertinent", hits[:3], parsed, notes)
        conf = "forte" if best.coverage >= 0.9 and best.ratio >= 0.6 else "partielle" if best.coverage >= 0.6 and best.ratio >= 0.38 else "faible"
        if conf == "partielle":
            notes.append("Correspondance partielle : vérifiez que ces passages répondent bien à votre question.")
        elif conf == "faible":
            notes.append("Correspondance FAIBLE : ces passages sont les plus proches trouvés mais peuvent ne pas répondre à la question "
                         "(le moteur ne comprend pas le sens, il compare des mots). Reformulez avec les termes du texte ou citez le numéro du texte.")
        return Result(question, True, "ok", hits, parsed, notes, conf)
    return Result(question, True, "ok", hits, parsed, notes, "forte")
