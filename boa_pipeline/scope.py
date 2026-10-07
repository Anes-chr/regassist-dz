"""Étape 3 : périmètre juridique et catalogue de documents candidats.

1. pages juridiques = hubs + BFS (profondeur limitée) sur les liens de contenu (hors menus)
2. tous les liens-documents trouvés sont dédupliqués par URL, classés, puis déclarés
   « dans le périmètre » ou « hors périmètre » AVEC la raison (rien n'est ignoré silencieusement).
"""
import re
from collections import Counter, defaultdict, deque
from urllib.parse import unquote

from . import config as C
from .classify import classify_link, clean_label, NORMATIVE
from .util import read_json, write_json, now_iso


def legal_pages(pages: dict) -> dict:
    """url -> profondeur depuis un hub."""
    seeds = list(C.LEGAL_HUBS)
    for u in pages:  # hubs arabes : slug commençant par /ar/ + « الإطار »
        if C.LEGAL_HUB_AR_HINT in u.lower() and "/ar/" in u:
            seeds.append(u)
    depth = {s: 0 for s in seeds if s in pages}
    q = deque(depth)
    while q:
        u = q.popleft()
        if depth[u] >= C.LEGAL_BFS_DEPTH:
            continue
        for l in pages[u].get("links", []):
            v = l["url"]
            if l["in_nav"] or v in depth or v not in pages:
                continue
            depth[v] = depth[u] + 1
            q.append(v)
    return depth


def build_candidates() -> dict:
    pages = read_json(C.STATE_DIR / "pages.json", {})
    lp = legal_pages(pages)
    by_url = defaultdict(list)
    for pu, p in pages.items():
        for d in p.get("docs", []):
            by_url[d["url"]].append({**d, "page": pu, "page_title": p.get("h1") or p.get("title"),
                                     "from_legal_page": pu in lp and not d["in_nav"]})
    cands, out_of_scope = [], []
    reasons = Counter()
    for url, srcs in by_url.items():
        if any(s["external"] for s in srcs):
            reasons["external_domain"] += 1
            out_of_scope.append({"url": url, "reason": "external_domain"}); continue
        # source principale : lien « de contenu » depuis une page juridique, avec le libellé le plus long
        legal_srcs = [s for s in srcs if s["from_legal_page"]]
        pool = legal_srcs or [s for s in srcs if not s["in_nav"]] or srcs
        best = max(pool, key=lambda s: len(clean_label(s["anchor"])))
        cls = classify_link(url, best["anchor"], best["page"], best["context_heading"])
        if not cls["title"] or cls["title"].lower() in {"télécharger", "telecharger", "download", "(embed)"}:
            alt = max((clean_label(s["anchor"]) for s in srcs), key=len, default="")
            cls["title"] = alt or unquote(url.rsplit("/", 1)[-1])
        title = cls["title"]
        non_legal = bool(re.search(C.NON_LEGAL_TITLE, title + " " + unquote(url), re.I))
        normative = cls["type_code"] in NORMATIVE and cls["type_source"] == "label"
        if legal_srcs and not (non_legal and not normative):
            reason = "page_juridique"
        elif normative and not non_legal:
            reason = "type_juridique_dans_libelle"
        else:
            r = "libelle_non_normatif" if non_legal else "hors_pages_juridiques_et_sans_type_juridique"
            reasons[r] += 1
            out_of_scope.append({"url": url, "reason": r, "title": title, "ext": best["ext"],
                                 "pages": [s["page"] for s in srcs][:5]})
            continue
        reasons["in_scope:" + reason] += 1
        cands.append({
            **cls, "url": url, "ext": best["ext"], "scope_reason": reason,
            "source_page": best["page"], "source_page_title": best["page_title"],
            "all_source_pages": sorted({s["page"] for s in srcs}),
            "all_anchors": sorted({clean_label(s["anchor"]) for s in srcs if s["anchor"]}),
        })
    cands.sort(key=lambda c: c["url"])
    res = {"generated_at": now_iso(), "legal_pages_count": len(lp), "legal_pages": lp,
           "candidates": cands, "out_of_scope": out_of_scope, "reasons": dict(reasons)}
    write_json(C.STATE_DIR / "candidates.json", res)
    return res
