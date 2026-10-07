"""Statut juridique des dispositions et séries périodiques — dérivés UNIQUEMENT de preuves présentes dans le corpus.

Le site de la Banque d'Algérie ne publie aucun statut de vigueur. Ce module n'invente donc rien : chaque statut est justifié par une règle documentée
(R-*, S-*, A-*, U-*), une preuve (citation, page) et un niveau de confiance. Dans le doute : UNKNOWN, et l'agent ne présente pas la disposition comme applicable.

Statuts : ACTIVE, MODIFIED, REPLACED, ABROGATED, HISTORICAL, UNKNOWN (voir RULES).
Deux niveaux : `documents` (par texte) et `articles` (par article, quand un texte ultérieur le vise expressément).
Sortie : legal_status.json à côté de documents_fr.json (dossier du corpus, ou AGENT_CORPUS_DIR).
Usage : python -m agent_fr.legal_status [--corpus DOSSIER]   (par défaut : corpus vivant)
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from boa_pipeline.relations import num_key

ROOT = Path(__file__).resolve().parent.parent
STATUTS = ("ACTIVE", "MODIFIED", "REPLACED", "ABROGATED", "HISTORICAL", "UNKNOWN")
VERSION = "legal_status/1"

RULES = {
    "R-ABR-TITRE": "ABROGATED, confiance HIGH : l'INTITULÉ d'un texte du corpus déclare qu'il abroge ce texte en entier.",
    "R-ABR-TEXTE": "ABROGATED, confiance MEDIUM : le TEXTE d'un texte ultérieur du corpus déclare abroger ce texte (citation à l'appui, pas de réserve « partiellement »).",
    "R-REP-TITRE": "REPLACED, confiance HIGH : l'intitulé d'un texte ultérieur déclare qu'il remplace ce texte en entier.",
    "R-REP-TEXTE": "REPLACED, confiance MEDIUM : le texte d'un texte ultérieur déclare remplacer ce texte en entier.",
    "R-MOD-TITRE": "MODIFIED, confiance HIGH : l'intitulé d'un texte ultérieur déclare modifier / compléter ce texte.",
    "R-MOD-TEXTE": "MODIFIED, confiance MEDIUM : le texte d'un texte ultérieur déclare modifier / compléter ce texte (ou une partie : relation « partielle »).",
    "R-ART-REMPL": "Article REPLACED, confiance MEDIUM : un texte ultérieur déclare « l'article N du <texte> est modifié et rédigé comme suit » (ou remplacé).",
    "R-ART-COMPL": "Article MODIFIED, confiance MEDIUM : un texte ultérieur déclare « l'article N du <texte> est complété ».",
    "R-ART-ABR": "Article ABROGATED, confiance MEDIUM : un texte ultérieur déclare « l'article N du <texte> est abrogé ».",
    "A-DERNIER": "ACTIVE, confiance MEDIUM : dernier texte connu d'une chaîne documentée (il en modifie/abroge/remplace un autre) et aucun texte du corpus ne l'affecte. "
                 "Ne prouve pas la vigueur : le corpus peut être incomplet.",
    "A-ART-COURANT": "ACTIVE, confiance MEDIUM : dernière rédaction connue d'un article modifié par une suite de textes (chaîne A→B→C).",
    "S-ECHUE": "HISTORICAL, confiance HIGH : série périodique (même intitulé, période explicite dans le texte, ex. « fixé pour l'exercice 2012 ») ; période échue. "
               "Les valeurs d'une série ne s'abrogent PAS entre elles : chaque texte vaut pour sa période.",
    "S-DERNIERE": "ACTIVE, confiance MEDIUM : dernière période PUBLIÉE d'une série périodique (la période suivante peut exister hors corpus).",
    "U-ISOLE": "UNKNOWN : aucune relation ni période explicite dans le corpus ; la vigueur ne peut pas être déterminée. Le texte ne doit pas être présenté comme actuellement applicable.",
    "U-INCOHERENT": "UNKNOWN : une relation existe mais sa date est incohérente (le texte « modificateur » est antérieur au texte visé).",
}

# --------------------------------------------------------------------- séries périodiques
PERIOD_PATTERNS = [
    (re.compile(r"pour\s+les\s+exercices?\s+(\d{4})\s+et\s+(\d{4})", re.I), "exercice"),
    (re.compile(r"pour\s+l['’]\s*exercice\s+(\d{4})", re.I), "exercice"),
    (re.compile(r"(premier|deuxi[èe]me|second|1er|2[èe]me|2nd)\s+semestre\s+(?:de\s+l['’]\s*ann[ée]e\s+)?(\d{4})", re.I), "semestre"),
    (re.compile(r"(?:au\s+titre\s+de|pour)\s+l['’]\s*ann[ée]e\s+(\d{4})", re.I), "année"),
]


def norm_title(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"(instruction|r[èe]glement|note|d[ée]cision)\s*n\s*[°ºo]?\s*[\d\-/ ]+(\s*du)?", "", t)
    t = re.sub(r"\d+(er)?\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+\d{4}", "", t)
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"[^a-zàâçéèêëîïôûùüÿ#' ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def extract_period(texts: list[str]):
    """(sorte, début, fin, citation) de la période déclarée par le texte, ou None. On prend la première occurrence."""
    for txt in texts:
        for rx, kind in PERIOD_PATTERNS:
            m = rx.search(txt)
            if not m:
                continue
            g = m.groups()
            if kind == "exercice":
                a, b = int(g[0]), int(g[-1])
                return kind, a, b, re.sub(r"\s+", " ", txt[max(0, m.start() - 30):m.end() + 20])
            if kind == "semestre":
                y = int(g[1])
                half = 1 if re.match(r"(premier|1)", g[0], re.I) else 2
                return kind, y + (half - 1) * 0.5, y + (half - 1) * 0.5, re.sub(r"\s+", " ", txt[max(0, m.start() - 30):m.end() + 20])
            y = int(g[0])
            return kind, y, y, re.sub(r"\s+", " ", txt[max(0, m.start() - 30):m.end() + 20])
    return None


def cluster_titles(titles: dict, threshold: float = 0.7) -> dict:
    """Regroupe les intitulés quasi identiques (Jaccard des mots ≥ seuil) : « Société de garantie » / « Fonds de garantie » restent dans la même série."""
    groups = {}
    stop = {"note", "notes", "aux", "banques", "et", "établissements", "financiers", "n", "du", "de", "la", "le", "les", "des", "d", "l", "relative", "relatif", "portant", "au", "a", "à"}
    for w, t in titles.items():
        toks = {x for x in t.split() if x not in stop}
        if not toks:
            continue
        for key, (ktoks, members) in groups.items():
            if len(toks & ktoks) / len(toks | ktoks) >= threshold:
                members.append(w)
                break
        else:
            groups[t] = (toks, [w])
    return {k: v[1] for k, v in groups.items()}


# --------------------------------------------------------------------- amendements au niveau de l'article
_VERB = r"(modifi[ée]e?s?|compl[ée]t[ée]e?s?|abrog[ée]e?s?|remplac[ée]e?s?|substitu[ée]e?s?)"
_AMEND_RE = re.compile(
    r"article\s+(\d+(?:\s*(?:bis|ter|quater))?)\s+(?:du|de\s+l['’]\s*|de\s+la\s+)?\s*"
    r"(r[èe]glement|instruction|loi|ordonnance|d[ée]cret|note)\s+n\s*[°º]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4})"
    r"([^.;:«\"]{0,180}?)\s+(?:(?:est|sont)\s+" + _VERB + r"|et\s+" + _VERB + r"(?=[^.]{0,12}comme\s+suit))", re.I)


def amendments(text: str):
    out = []
    for m in _AMEND_RE.finditer(text or ""):
        verb = (m.group(5) or m.group(6)).lower()
        v = "complete" if verb.startswith("compl") else "abroge" if verb.startswith("abrog") else "remplace" if verb.startswith(("remplac", "substitu")) else "modifie"
        # « modifié et complété » : réécriture (REPLACED) ; « complété » seul : ajout (MODIFIED)
        window = text[m.start():m.end() + 80].lower()
        if v == "complete" and re.search(r"modifi[ée]e?s?\s+et\s+compl|compl[ée]t[ée]e?s?\s+et\s+modifi", window):
            v = "modifie"
        typ = {"règlement": "règlement", "reglement": "règlement", "décret": "décret", "decret": "décret"}.get(m.group(2).lower(), m.group(2).lower())
        num = re.sub(r"\s+", "", m.group(3).replace("–", "-").replace("/", "-"))
        out.append({"verbe": v, "type": typ, "numero": num_key(num), "article": re.sub(r"\s+", " ", m.group(1).strip().lower()),
                    "citation": re.sub(r"\s+", " ", text[max(0, m.start() - 10):m.end() + 60])})
    return out


# --------------------------------------------------------------------- calcul
def build(docs: list[dict], chunks: list[dict]) -> dict:
    fr_docs = [d for d in docs if d.get("language") in (None, "fr") and "~" not in d["document_id"]]
    by_work = {}
    for d in fr_docs:
        by_work.setdefault(d["work_id"], d)
    works_by_ident = defaultdict(list)                        # (type, clé du numéro) -> work_id
    for w, d in by_work.items():
        if d.get("number"):
            works_by_ident[(d["document_type"], num_key(d["number"]))].append(w)
    fr_chunks = [c for c in chunks if "~" not in c["document_id"] and c.get("language") in (None, "fr")]
    texts_by_work = defaultdict(list)
    for c in fr_chunks:
        texts_by_work[c["work_id"]].append(c["text"])

    # ---- séries périodiques
    groups = cluster_titles({w: norm_title(d["title"]) for w, d in by_work.items()})
    series, member_of = {}, {}
    for key, ws in groups.items():
        if len(ws) < 3 or not key:
            continue
        periods = {w: extract_period(texts_by_work[w]) for w in ws}
        have = [w for w in ws if periods[w]]
        if len(have) < 3 or len(have) < 0.8 * len(ws):
            continue                                           # pas assez de preuves de périodicité : ce n'est pas traité comme une série
        kinds = {periods[w][0] for w in have}
        if len(kinds) != 1:
            continue
        sid = "SER-" + re.sub(r"\W+", "-", key)[:48].strip("-")
        members = sorted(({"work_id": w, "date": by_work[w].get("date"), "sorte": periods[w][0], "debut": periods[w][1], "fin": periods[w][2], "preuve": periods[w][3]}
                          for w in have), key=lambda m: (m["fin"], m["date"] or ""))
        series[sid] = {"intitule_type": key, "sorte": kinds.pop(), "membres": members, "derniere_periode": members[-1]["fin"],
                       "regle": "S-ECHUE / S-DERNIERE", "non_classes": sorted(set(ws) - set(have))}
        for m in members:
            member_of[m["work_id"]] = (sid, m)

    # ---- relations au niveau du texte
    docs_out = {}
    for w, d in by_work.items():
        evid, status, conf, rule, note = [], "UNKNOWN", "LOW", "U-ISOLE", ""
        incoming = []
        for key, kind in (("abroge_par", "abroge"), ("remplace_par", "remplace"), ("modifie_par", "modifie"), ("complete_par", "complete")):
            for e in d.get(key, []):
                if e.get("work_id") and e["work_id"] != w:
                    incoming.append((kind, e))
        coherent = []
        for kind, e in incoming:
            if e.get("date") and d.get("date") and e["date"] < d["date"]:
                note = "relation à date incohérente ignorée : " + e["work_id"]
                continue
            coherent.append((kind, e))
        order = {"abroge": 0, "remplace": 1, "modifie": 2, "complete": 2}
        coherent.sort(key=lambda ke: (order[ke[0]], ke[1].get("evidence", {}).get("source") != "title", ke[1].get("partial", False)))
        if coherent:
            kind, e = coherent[0]
            if kind == "abroge" and any(k2 == "remplace" and x["work_id"] == e["work_id"] and not x.get("partial") for k2, x in coherent):
                kind = "remplace"                  # « abroge ET REMPLACE » : le texte est REMPLACÉ (pas simplement abrogé sans suite)
            src = e.get("evidence", {}).get("source", "text")
            partial = bool(e.get("partial"))
            if kind == "abroge" and not partial:
                status, conf, rule = "ABROGATED", ("HIGH" if src == "title" else "MEDIUM"), ("R-ABR-TITRE" if src == "title" else "R-ABR-TEXTE")
            elif kind == "remplace" and not partial:
                status, conf, rule = "REPLACED", ("HIGH" if src == "title" else "MEDIUM"), ("R-REP-TITRE" if src == "title" else "R-REP-TEXTE")
            else:
                status, conf, rule = "MODIFIED", ("HIGH" if (src == "title" and not partial) else "MEDIUM"), ("R-MOD-TITRE" if (src == "title" and not partial) else "R-MOD-TEXTE")
            evid = [{"relation": k, "par": x["work_id"], "date": x.get("date"), "source": x.get("evidence", {}).get("source"),
                     "partielle": bool(x.get("partial")), "page": x.get("evidence", {}).get("page"),
                     "citation": x.get("evidence", {}).get("quote")} for k, x in coherent[:6]]
        elif incoming and not coherent:
            status, conf, rule = "UNKNOWN", "LOW", "U-INCOHERENT"
        else:
            outgoing = any(d.get(k) for k in ("abroge", "remplace", "modifie", "complete"))
            if outgoing:
                status, conf, rule = "ACTIVE", "MEDIUM", "A-DERNIER"
        s_info = member_of.get(w)
        if s_info:
            sid, m = s_info
            last = series[sid]["membres"][-1]["work_id"] == w
            if status in ("UNKNOWN", "ACTIVE", "MODIFIED"):
                if last:
                    status, conf, rule = "ACTIVE", "MEDIUM", "S-DERNIERE"
                else:
                    status, conf, rule = "HISTORICAL", "HIGH", "S-ECHUE"
                evid = [{"serie": sid, "periode": f"{m['sorte']} {m['debut']}" + ("" if m["debut"] == m["fin"] else f"–{m['fin']}"), "citation": m["preuve"]}]
        entry = {"statut": status, "confiance": conf, "regle": rule, "preuves": evid}
        if s_info:
            entry["serie"] = s_info[0]
            entry["periode"] = {"sorte": s_info[1]["sorte"], "debut": s_info[1]["debut"], "fin": s_info[1]["fin"]}
        if note:
            entry["note"] = note
        docs_out[w] = entry

    # ---- articles : amendements explicites
    amenders = defaultdict(list)                               # (work cible, article) -> [(date, work, article, verbe, citation)]
    unresolved = 0
    for c in fr_chunks:
        if c["unit_kind"] not in ("article", "body", "annexe", "preamble"):
            continue
        for a in amendments(c["text"]):
            targets = works_by_ident.get((a["type"], a["numero"]), [])
            if len(targets) != 1 or targets[0] == c["work_id"]:
                unresolved += 1
                continue
            amenders[(targets[0], a["article"])].append((c.get("date") or "", c["work_id"], c.get("article"), a["verbe"], a["citation"], c.get("page_number")))
    arts = {}
    for (tw, art), lst in amenders.items():
        lst = sorted(set(lst))
        # cibles : l'article d'origine reçoit le statut du DERNIER amendement ; chaque amendement intermédiaire est REPLACED par le suivant
        chain = [("origine", tw, art, None, None)] + [("amend", w, a2, v, cit) for (_, w, a2, v, cit, _) in lst]
        last_rewrite = max((i for i, x in enumerate(chain) if x[0] == "amend" and x[3] in ("modifie", "remplace", "abroge")), default=None)
        for i, (kind, w, a2, v, cit) in enumerate(chain):
            key = f"{w}::{a2}"
            if kind == "origine":
                later = [x for x in chain[1:]]
                v_last = later[-1]
                if any(x[3] == "abroge" for x in later):
                    st, rl = "ABROGATED", "R-ART-ABR"
                elif any(x[3] in ("modifie", "remplace") for x in later):
                    st, rl = "REPLACED", "R-ART-REMPL"
                else:
                    st, rl = "MODIFIED", "R-ART-COMPL"
                arts.setdefault(key, {"statut": st, "confiance": "MEDIUM", "regle": rl,
                                      "preuves": [{"par": f"{x[1]}::{x[2]}", "verbe": x[3], "citation": x[4]} for x in later[:6]]})
            else:
                nxt = [x for x in chain[i + 1:] if x[3] in ("modifie", "remplace", "abroge")]
                if nxt:
                    st, rl = ("ABROGATED", "R-ART-ABR") if nxt[-1][3] == "abroge" else ("REPLACED", "R-ART-REMPL")
                    ent = {"statut": st, "confiance": "MEDIUM", "regle": rl, "preuves": [{"par": f"{nxt[0][1]}::{nxt[0][2]}", "verbe": nxt[0][3], "citation": nxt[0][4]}]}
                else:
                    ent = {"statut": "ACTIVE", "confiance": "MEDIUM", "regle": "A-ART-COURANT", "preuves": [{"citation": cit}]}
                ent["version_de"] = f"{tw}::{art}"
                arts[key] = ent
    return {"version": VERSION, "regles": RULES, "statuts": list(STATUTS), "series": series, "documents": docs_out, "articles": arts,
            "stats": {"textes": len(docs_out), "series": len(series), "articles_avec_statut": len(arts), "amendements_non_resolus": unresolved,
                      "par_statut": {s: sum(1 for v in docs_out.values() if v["statut"] == s) for s in STATUTS}}}


class Legal:
    """Accès en lecture au statut calculé (legal_status.json). Absent → tout est UNKNOWN : l'agent ne présente rien comme applicable."""

    def __init__(self, data: dict | None):
        data = data or {}
        self.documents = data.get("documents", {})
        self.articles = data.get("articles", {})
        self.series = data.get("series", {})
        self.available = bool(data)

    def status_for_chunk(self, chunk: dict) -> dict:
        """Statut le plus précis : article (si un texte ultérieur le vise) sinon texte. Toujours un dict {statut, confiance, regle, ...}."""
        art = chunk.get("article")
        if art is not None:
            a = self.articles.get(f"{chunk['work_id']}::{art}")
            if a:
                return dict(a, niveau="article")
        d = self.documents.get(chunk["work_id"])
        if d:
            return dict(d, niveau="texte")
        return {"statut": "UNKNOWN", "confiance": "LOW", "regle": "U-ISOLE", "preuves": [], "niveau": "texte"}

    def member(self, work_id: str):
        d = self.documents.get(work_id) or {}
        return (d.get("serie"), d.get("periode")) if d.get("serie") else (None, None)

    def series_latest(self, sid: str):
        s = self.series.get(sid)
        return s["derniere_periode"] if s else None


_LEGAL_CACHE = {}


def load_legal(path) -> Legal:
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns if path.exists() else None)
    if key not in _LEGAL_CACHE:
        _LEGAL_CACHE.clear()
        _LEGAL_CACHE[key] = Legal(json.loads(path.read_text(encoding="utf-8")) if path.exists() else None)
    return _LEGAL_CACHE[key]


def corpus_paths(corpus: str | None):
    if corpus:
        base = Path(corpus)
        return base / "documents_fr.json", base / "chunks_fr.jsonl", base / "legal_status.json"
    return (ROOT / "corpus" / "metadata" / "documents_fr.json", ROOT / "corpus" / "chunks" / "chunks_fr.jsonl", ROOT / "corpus" / "metadata" / "legal_status.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.environ.get("AGENT_CORPUS_DIR"))
    a = ap.parse_args()
    dpath, cpath, out = corpus_paths(a.corpus)
    docs = json.loads(dpath.read_text(encoding="utf-8"))
    docs = docs if isinstance(docs, list) else list(docs.values())
    chunks = [json.loads(l) for l in open(cpath, encoding="utf-8")]
    res = build(docs, chunks)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print("statuts :", json.dumps(res["stats"], ensure_ascii=False))
    print("écrit :", out)


if __name__ == "__main__":
    main()
