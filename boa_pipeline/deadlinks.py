"""Liens morts : diagnostic sans deviner d'URL.

Constat de la phase 3 : « 38 liens morts » = 19 URLs uniques comptées deux fois (étape de build + rapport de téléchargement), et ces 19 URLs sont d'anciens chemins `/pdf/<dossier>/<fichier>.pdf`
que le site a migrés vers `/stoodroa/<année>/<mois>/<fichier>.pdf` : le MÊME fichier existe dans le corpus sous son URL officielle actuelle (médiathèque du site).

Résolution (aucune URL n'est jamais remplacée ni inventée ; l'ancienne URL est conservée comme `dead_source_urls` du document) :
  MOVED_OFFICIAL  : un document du corpus porte le même NOM DE FICHIER sur une URL officielle du site (document_url, alias, médiathèque) ET le même type + numéro (confiance « forte »)
                    — ou le même nom de fichier seul quand l'intitulé du lien est tronqué (confiance « moyenne : nom de fichier seul ») ;
  BROKEN_SOURCE   : aucune source officielle retrouvée dans le corpus ; l'information est conservée (document absent du corpus).
"""
import re
from collections import defaultdict
from urllib.parse import unquote, urlsplit

from .relations import num_key


def _base(u: str) -> str:
    return unquote(urlsplit(u).path.rsplit("/", 1)[-1]).lower()


def _norm_title(t: str | None) -> str:
    return re.sub(r"[^a-z0-9؀-ۿ]+", " ", re.sub(r"[ً-ٰٟ]", "", (t or "").lower())).strip()


def _title_consistent(declared: str | None, d: dict) -> bool:
    """L'intitulé tronqué du lien (« réserves obligatoires. ») est-il contenu dans l'intitulé du document retrouvé ? (≥ 12 caractères significatifs)"""
    a = _norm_title(declared)
    if len(a) < 12:
        return False
    return any(a in _norm_title(x) for x in (d.get("title"), d.get("title_document")) if x)


def _urls_of(d: dict) -> list[str]:
    out = [d.get("document_url")]
    out += [a.get("url") if isinstance(a, dict) else a for a in d.get("alias_urls", []) or []]
    out += [a.get("url") for a in d.get("media_library_alternates", []) or []]
    return [u for u in out if u]


def reconcile(failed: list[dict], recs: list[dict], candidates: dict | None = None) -> list[dict]:
    """`failed` : entrées de documents_en_echec (peuvent répéter la même URL) ; `recs` : documents construits ; `candidates` : url -> candidat du périmètre (type, numéro, date)."""
    candidates = candidates or {}
    by_base = defaultdict(list)
    for d in recs:
        for u in _urls_of(d):
            by_base[_base(u)].append((d, u))
    merged = {}
    for f in failed:
        u = f.get("url")
        if not u:
            continue
        m = merged.setdefault(u, {"url": u, "title": f.get("title"), "stages": [], "reasons": []})
        m["stages"] = sorted(set(m["stages"]) | {f.get("stage") or "download"})
        if f.get("reason") and f["reason"] not in m["reasons"]:
            m["reasons"].append(f["reason"])
        if not m["title"] and f.get("title"):
            m["title"] = f["title"]
    out = []
    for u, m in merged.items():
        c = candidates.get(u) or {}
        m["source_pages"] = c.get("all_source_pages") or ([c["source_page"]] if c.get("source_page") else [])
        m["declared_type"], m["declared_number"], m["declared_date"] = c.get("type_code"), c.get("number"), c.get("date")
        hits = [(d, du) for d, du in by_base.get(_base(u), []) if du != u]
        docs = {}
        for d, du in hits:
            docs.setdefault(d["document_id"], (d, du))
        strong = [x for x in docs.values()
                  if c.get("number") and x[0].get("number") and x[0].get("type_code") == c.get("type_code") and num_key(x[0]["number"]) == num_key(c["number"])]
        by_title = [x for x in docs.values() if x not in strong and _title_consistent(m.get("title"), x[0])]
        if strong or by_title or docs:
            chosen = strong or by_title or list(docs.values())
            m["resolution"] = "MOVED_OFFICIAL"
            m["confidence"] = ("forte (nom de fichier + type + numéro)" if strong else "forte (nom de fichier + intitulé tronqué contenu dans l'intitulé du document)" if by_title
                               else "moyenne (nom de fichier identique ; intitulé du lien tronqué)")
            m["same_listing_page"] = any(x[0].get("source_url") in m["source_pages"] or any(p in m["source_pages"] for p in (x[0].get("all_source_urls") or [])) for x in chosen)
            if m["confidence"].startswith("moyenne") and m["same_listing_page"]:
                m["confidence"] = "moyenne+ (nom de fichier identique + même page de liste du site ; intitulé du lien tronqué)"
            m["resolved_documents"] = [{"document_id": d["document_id"], "work_id": d["work_id"], "official_url": du, "number": d.get("number"), "date": d.get("date")} for d, du in chosen]
            m["note"] = ("Ancien chemin du site (/pdf/…) ; le même fichier est servi sous l'URL officielle actuelle. L'ancienne URL est conservée dans `dead_source_urls` ; "
                         "aucune URL n'a été devinée : elle provient de la médiathèque du site déjà collectée.")
        else:
            m["resolution"] = "BROKEN_SOURCE"
            m["confidence"] = None
            m["resolved_documents"] = []
            m["note"] = "Aucune source officielle retrouvée dans le corpus pour ce lien : document absent. Information conservée, rien n'est remplacé."
        out.append(m)
    return sorted(out, key=lambda x: x["url"])


def attach_to_documents(moved: list[dict], recs: list[dict]):
    """Conserve l'ancienne URL morte dans les métadonnées du document retrouvé (jamais comme URL de référence)."""
    by_id = {d["document_id"]: d for d in recs}
    for m in moved:
        if m["resolution"] != "MOVED_OFFICIAL":
            continue
        for r in m["resolved_documents"]:
            d = by_id.get(r["document_id"])
            if d is not None:
                d.setdefault("dead_source_urls", [])
                if all(x["url"] != m["url"] for x in d["dead_source_urls"]):
                    d["dead_source_urls"].append({"url": m["url"], "status": "MOVED_OFFICIAL", "listed_on": m["source_pages"][:3]})
