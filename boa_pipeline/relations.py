"""Étapes 6-7 (suite) : relations entre textes (modifie / complète / abroge / remplace), versions,
appariement FR/AR et statut juridique.

Règle d'or : le statut n'est JAMAIS déduit sans preuve dans les sources collectées. Par défaut : « STATUT À VÉRIFIER ».
"""
import re
from collections import defaultdict
from pathlib import Path

from .classify import MONTHS, TYPES, detect_type, norm_number, parse_date, parse_day_month_ar, TYPE_LABEL

STATUS_UNKNOWN = "STATUT À VÉRIFIER"
REF_TYPES = r"(r[èe]glement|instruction|loi|ordonnance|d[ée]cret|d[ée]cision|note|circulaire|lignes?\s+directrices?)"
REF_RE = re.compile(REF_TYPES + r"\s+(?:\w+\s+)?n\s*[°ºo]?\s*[°º]?\s*[:.]?\s*(\d{1,4}\s*[-/–]\s*\d{1,4}(?:\s*[-/–]\s*\d{1,4})?)"
                    r"(?:\s*(?:du|en date du|datée? du)\s+(\d{1,2}|1er)\s*(?:er)?\s+([a-zéûôèà]+)\s+(\d{4}))?", re.I)
VERBS = [
    ("modifie", r"modifi\w*|portant\s+modification"),
    ("complete", r"compl[éeè]t\w*|compl[eé]ter|ajout\w*"),
    ("abroge", r"abrog\w*|portant\s+abrogation"),
    ("remplace", r"remplac\w*|se\s+substitu\w*|substitu\w*"),
]
VERB_RE = [(k, re.compile(r"\b(?:" + v + r")", re.I)) for k, v in VERBS]
PARTIAL_RE = re.compile(r"certaines?\s+dispositions|article[s]?\s+\d|alin[ée]a|paragraphe", re.I)   # « les dispositions du règlement X sont abrogées » = abrogation totale
PASSIVE_RE = re.compile(r"(?:est|sont|se\s+trouve\w*)\s+(abrog\w+|remplac\w+|modifi\w+|compl[ée]t\w+)", re.I)
INV = {"modifie": "modifie_par", "complete": "complete_par", "abroge": "abroge_par", "remplace": "remplace_par"}
TYPE_FROM_WORD = {"règlement": "REG", "reglement": "REG", "instruction": "INS", "loi": "LOI", "ordonnance": "ORD",
                  "décret": "DEC", "decret": "DEC", "décision": "DCS", "decision": "DCS", "note": "NOT",
                  "circulaire": "CIR", "lignes directrices": "LD", "ligne directrice": "LD", "lignes directrice": "LD"}


def type_code_from_word(w: str) -> str:
    w = re.sub(r"\s+", " ", w.lower())
    return TYPE_FROM_WORD.get(w, "OTH")


def num_key(num: str | None):
    if not num:
        return None
    return tuple(p[-2:] if len(p) == 4 else p.zfill(2) for p in re.split(r"[-/]", num))


def _date_iso(d, mon, y):
    if not (d and mon and y):
        return None
    iso, _ = parse_date(f"{d} {mon} {y}")
    return iso


def find_relations(text: str, source: str, page: int | None = None) -> list[dict]:
    """Relations déclarées dans `text`. source = 'title' (preuve forte) | 'text' (preuve à vérifier)."""
    out = []
    refs = list(REF_RE.finditer(text))
    prev_end, prev_verbs = 0, []
    for m in refs:
        seg = text[prev_end:m.start()]
        if source == "text":   # on ne garde que la proposition qui précède la référence
            seg = re.split(r"[.;]\s", seg)[-1]
            if re.search(r"(?!\w)vu(?!\w)", seg, re.I):
                prev_end, prev_verbs = m.end(), []
                continue
        verbs = [k for k, rx in VERB_RE if rx.search(seg)]
        if source == "text" and verbs and not re.search(r"pr[ée]sent|ci-apr[èe]s|sont\s|est\s", seg, re.I):
            verbs = []   # « le règlement A complétant le règlement B » : le verbe ne concerne pas CE document
        if not verbs and prev_verbs and len(seg.strip()) <= 30 and not re.search(r"\bvu\b", seg, re.I):
            verbs = prev_verbs   # « modifiant le règlement A et le règlement B »
        if not verbs:
            pm = PASSIVE_RE.search(re.split(r"[.;]\s", text[m.end():m.end() + 160])[0]) if source == "text" else None   # « …du 2 Ramadhan 1418 correspondant au…, susvisé, sont abrogées »
            if pm:
                verbs = [k for k, rx in VERB_RE if rx.search(pm.group(1))]
        prev_end, prev_verbs = m.end(), verbs
        if not verbs:
            continue
        ref = {"type_code": type_code_from_word(m.group(1)), "number": norm_number(m.group(2)),
               "date": _date_iso(m.group(3), m.group(4), m.group(5)),
               "raw": re.sub(r"\s+", " ", m.group(0))}
        partial = bool(PARTIAL_RE.search(seg))
        q0 = max(0, m.start() - 120)
        for v in dict.fromkeys(verbs):
            out.append({"relation": v, "target_ref": ref, "partial": partial,
                        "evidence": {"source": source, "page": page,
                                     "quote": re.sub(r"\s+", " ", text[q0:m.end() + 40]).strip()}})
    return out


def resolve(ref: dict, index: dict, self_id: str):
    """Résout une référence (type + numéro [+ date]) vers un work_id du corpus.
    Le numéro contient déjà l'année (« 09-96 ») : la date sert à départager plusieurs textes, pas à exclure — les libellés du site
    et les textes citants divergent parfois sur la date (ex. 09-96 : « 1995 » / « 1996 »)."""
    cands = [c for c in index.get((ref["type_code"], num_key(ref["number"])), []) if c["work_id"] != self_id]
    if ref.get("date"):
        exact = [c for c in cands if c.get("date") == ref["date"]]
        if exact:
            cands = exact
    works = {c["work_id"] for c in cands}
    return sorted(works)[0] if len(works) == 1 else None


OVERRIDES_FILE = Path(__file__).with_name("twin_overrides.json")


def _year_part_matches(number: str | None, year: int) -> bool:
    """Le numéro (« 04-04 », « 2004-04 », « 92-10 ») contient-il l'année de la date (en 2 ou 4 chiffres) ? Garde-fou du rattachement par jour-mois."""
    return any(p in (str(year), str(year)[-2:]) for p in re.split(r"[-/]", number or ""))


def pair_twins(docs: list[dict]) -> list[dict]:
    """Rattachement FR/AR d'un même texte quand leurs dates ne sont pas identiques ALORS QUE l'identité du texte est démontrable. Règles (aucune similarité de contenu) :
      R-TWIN-DATE        même type, même numéro, même date -> même work_id (comportement d'origine, via assign_ids) ;
      R-TWIN-JOURMOIS    un seul document AR sans date complète (l'année manque dans le libellé du site) ; UN SEUL texte FR de même type + même numéro ; jour et mois du libellé arabe
                         = jour et mois de la date française ; l'année de la date française figure dans le numéro. On recopie la date FR sur le document AR avec la preuve ;
      R-TWIN-CONFIRME    appariement confirmé par un humain dans twin_overrides.json (champ `confirmed_by` renseigné).
    Un conflit de dates (même type + même numéro, dates complètes différentes) n'est JAMAIS tranché automatiquement : il est signalé (`twin_status`) et proposé à l'arbitrage humain."""
    by_key = defaultdict(list)
    for d in docs:
        if d.get("number"):
            by_key[(d["type_code"], num_key(d["number"]))].append(d)
    log = []
    for key, ds in by_key.items():
        frs = [d for d in ds if d["language"] == "fr"]
        ars = [d for d in ds if d["language"] == "ar"]
        fr_dates = sorted({d["date"] for d in frs if d.get("date")})
        for a in ars:
            if a.get("date") and a["date"] in fr_dates:
                continue                                                                  # R-TWIN-DATE : déjà rattachés
            dm = parse_day_month_ar(a["title"]) if not a.get("date") else None
            if dm and len(fr_dates) == 1 and len(ars) == 1:
                y, m, dd = (int(x) for x in fr_dates[0].split("-"))
                if (dd, m) == dm and _year_part_matches(a["number"], y):
                    a["date_before_pairing"] = a.get("date")
                    a["date"], a["date_raw"], a["date_source"] = fr_dates[0], f"{dm[0]}/{dm[1]} (libellé arabe) + année du jumeau FR", "jumeau_FR(jour-mois du libellé + numéro)"
                    a["twin_rule"] = "R-TWIN-JOURMOIS"
                    log.append({"rule": "R-TWIN-JOURMOIS", "ar": a["title"][:90], "fr_date": fr_dates[0], "label_day_month": list(dm)})
                    continue
            if frs and (a.get("date") and fr_dates and a["date"] not in fr_dates):
                a["twin_status"] = "CONFLIT_DE_DATE:" + ",".join(sorted(d["document_url"] for d in frs))
            elif frs and not a.get("date"):
                a["twin_status"] = "AUCUN_INDICE_DE_DATE"
    return log


def apply_twin_overrides(docs: list[dict]) -> list[dict]:
    """Appariements confirmés PAR UN HUMAIN (twin_overrides.json, `confirmed` non vide) ; les propositions non confirmées ne sont jamais appliquées."""
    if not OVERRIDES_FILE.exists():
        return []
    import json
    conf = [x for x in json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")).get("confirmed", []) if x.get("confirmed_by")]
    by_url = {d["document_url"]: d for d in docs}
    log = []
    for x in conf:
        a, f = by_url.get(x["ar_url"]), by_url.get(x["fr_url"])
        if a and f and f.get("date"):
            a["date_before_pairing"] = a.get("date")
            a["date"], a["date_source"], a["twin_rule"] = f["date"], "jumeau_FR(confirmé par " + x["confirmed_by"] + ")", "R-TWIN-CONFIRME"
            log.append({"rule": "R-TWIN-CONFIRME", "ar": a["title"][:90], "fr_date": f["date"], "by": x["confirmed_by"]})
    return log


def assign_ids(docs: list[dict]):
    """work_id (texte juridique) et document_id (version linguistique). FR et AR d'un même texte partagent le work_id."""
    apply_twin_overrides(docs)
    pair_twins(docs)
    groups = defaultdict(list)
    for d in docs:
        if d["number"]:
            groups[(d["type_code"], num_key(d["number"]), d.get("date") or "")].append(d)
    used = {}
    for key, ds in groups.items():
        t, nk, date = key
        base = f"{t}-{'-'.join(nk)}"
        # même type+numéro mais dates différentes => on ajoute la date pour distinguer deux textes distincts
        same_num = [k for k in groups if k[0] == t and k[1] == nk]
        wid = base + (f"-{date.replace('-', '')}" if len(same_num) > 1 and date else "")
        for d in ds:
            d["work_id"] = wid
    for d in docs:
        if not d.get("work_id"):
            d["work_id"] = f"{d['type_code']}-NA-{d['url_hash'][:8]}"
    for d in docs:
        lang = d["language"] if d["language"] in ("fr", "ar") else "und"
        d["work_id"] = re.sub(r"[^A-Za-z0-9._-]+", "_", d["work_id"])
        did = f"{d['work_id']}.{lang}"
        n = used.get(did, 0)
        used[did] = n + 1
        d["document_id"] = did if n == 0 else f"{did}~{n + 1}"   # collision = autre fichier même texte/langue (version/doublon)


def link_documents(docs: list[dict]):
    """Calcule relations sortantes/entrantes, versions et statut."""
    index = defaultdict(list)
    for d in docs:
        index[(d["type_code"], num_key(d["number"]))].append(d)
    by_work = defaultdict(list)
    for d in docs:
        by_work[d["work_id"]].append(d)
    for d in docs:
        d["relations_out"] = []
        d["unresolved_references"] = []
    for d in docs:
        rels = find_relations(d["title"], "title")
        if d.get("title_document"):
            rels += find_relations(d["title_document"], "title")
        for u in d.get("_units", []):
            if u["kind"] in ("article", "body", "annexe"):
                for pg_text in [u["text"]]:
                    rels += find_relations(pg_text, "text", u["page_start"])
        seen = set()
        for r in rels:
            tgt = resolve(r["target_ref"], index, d["work_id"])
            key = (r["relation"], r["target_ref"]["type_code"], r["target_ref"]["number"], r["evidence"]["source"])
            if key in seen:
                continue
            seen.add(key)
            r["target_work_id"] = tgt
            d["relations_out"].append(r)
            if tgt is None:
                d["unresolved_references"].append({k: r["target_ref"][k] for k in ("type_code", "number", "date", "raw")} |
                                                  {"relation": r["relation"]})
    # versions arabes : l'extraction de relations est faite sur le français ; on recopie (avec la provenance) vers
    # la version AR du même texte afin que les deux versions portent les mêmes relations
    for wid, ds in by_work.items():
        donors = [x for x in ds if x["relations_out"] and x["language"] == "fr"]
        for d in ds:
            if not d["relations_out"] and donors:
                src = donors[0]
                d["relations_out"] = [dict(r, evidence=dict(r["evidence"], copied_from=src["document_id"])) for r in src["relations_out"]]
                d["unresolved_references"] = list(src["unresolved_references"])
    # inverses (au niveau du texte = work_id, pas de la langue)
    inbound = defaultdict(list)
    for d in docs:
        for r in d["relations_out"]:
            if r["target_work_id"]:
                inbound[r["target_work_id"]].append((d, r))
    for d in docs:
        d["abroge"], d["modifie"], d["complete"], d["remplace"] = [], [], [], []
        for r in d["relations_out"]:
            ent = {"work_id": r["target_work_id"], "reference": r["target_ref"]["raw"], "partial": r["partial"],
                   "evidence": r["evidence"]}
            d[r["relation"]].append(ent)
        d["abroge_par"], d["modifie_par"], d["complete_par"], d["remplace_par"] = [], [], [], []
        # le document source d'une relation entrante est la version FRANÇAISE (hors copie ~N) quand elle existe : les relations arabes sont des COPIES de celles du français ; sans cet ordre, la
        # déduplication gardait parfois le jumeau arabe, et la remontée du texte modificateur (add_modifiers) cherchait un renvoi d'article français dans des chunks arabes (31 relations, phase 3)
        for src, r in sorted(inbound.get(d["work_id"], []), key=lambda x: (x[0]["language"] != "fr", "~" in x[0]["document_id"], x[0]["document_id"])):
            if src["work_id"] == d["work_id"]:
                continue
            d[INV[r["relation"]]].append({"work_id": src["work_id"], "document_id": src["document_id"],
                                          "date": src.get("date"), "partial": r["partial"], "evidence": r["evidence"]})
        for k in ("abroge_par", "modifie_par", "complete_par", "remplace_par"):
            d[k] = _dedup_rel(d[k])
        d["status"], d["status_evidence"], d["status_note"] = compute_status(d)
        siblings = [x for x in by_work[d["work_id"]] if x is not d]
        d["same_work_documents"] = sorted({x["document_id"] for x in siblings})
    # compat. noms français demandés (accents) dans la sortie JSON
    for d in docs:
        d["complété_par"] = d["complete_par"]; d["modifié_par"] = d["modifie_par"]
        d["abrogé_par"] = d["abroge_par"]; d["remplacé_par"] = d["remplace_par"]
        d["complète"] = d["complete"]


def _dedup_rel(lst):
    seen, out = set(), []
    for e in lst:
        k = (e["work_id"], e["evidence"]["source"])
        if k not in seen:
            seen.add(k); out.append(e)
    return out


def compute_status(d: dict):
    strong = [e for k in ("abroge_par", "remplace_par") for e in d[k]
              if not e["partial"] and e["evidence"]["source"] == "title"]
    if strong:
        return ("abrogé", strong,
                "Abrogation/remplacement explicite dans l'intitulé d'un texte officiel du corpus ; "
                "date d'effet à vérifier dans le texte abrogeant.")
    weak = [e for k in ("abroge_par", "remplace_par") for e in d[k]]
    if weak:
        return (STATUS_UNKNOWN, weak, "Une abrogation/un remplacement (ou une abrogation partielle) est évoqué dans un texte "
                "du corpus mais n'est pas établi sans ambiguïté : vérification humaine requise.")
    if d["type_code"] in ("COM", "AVI", "NOT"):
        pass
    note = "Aucune source officielle collectée n'indique l'abrogation, mais le site ne publie pas de statut de vigueur : " \
           "l'applicabilité actuelle ne peut pas être affirmée."
    if d["modifie_par"] or d["complete_par"]:
        note += " Ce texte a été modifié/complété : consulter aussi les textes listés dans modifié_par / complété_par."
    return STATUS_UNKNOWN, [], note
