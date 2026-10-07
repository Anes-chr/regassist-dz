"""Étape 1-2 : crawler + découverte d'URLs.

Sources de découverte : sitemaps WordPress, liens internes (BFS), hubs juridiques.
Produit state/pages.json (index des pages et de leurs liens) et reports/crawl_report.json.
Les pages HTML sont mises en cache dans corpus/raw/html pour permettre un relancement incrémental.
"""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, deque
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup

from . import config as C
from .client import Client, normalize_url, ext_of
from .util import now_iso, read_json, write_json

REUSE_SECONDS = 6 * 3600   # un relancement dans les 6 h réutilise le cache sans requête
NAV_CLASS_HINTS = ("menu", "ekit-", "elementor-location-header", "elementor-location-footer", "breadcrumb")


def url_key(u: str) -> str:
    return hashlib.sha1(u.encode()).hexdigest()


def sitemap_urls(client: Client, report: dict) -> list[str]:
    out, queue, seen = [], [C.BASE + "/wp-sitemap.xml"], set()
    while queue:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = client.get(sm)
        if r is None or r.status_code != 200:
            report["sitemap_failures"].append(sm)
            continue
        report["sitemaps_read"].append(sm)
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            report["sitemap_failures"].append(sm)
            continue
        for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            u = loc.text.strip()
            (queue if u.endswith(".xml") else out).append(u)
    return out


def is_nav(a) -> bool:
    for p in a.parents:
        if p.name in ("nav", "header", "footer"):
            return True
        cls = " ".join(p.get("class", [])) if hasattr(p, "get") else ""
        if cls and any(h in cls for h in NAV_CLASS_HINTS):
            return True
    return False


def parse_page(html: bytes, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "")
    h1 = soup.find("h1")
    lang = (soup.html.get("lang") or "") if soup.html else ""
    docs, links = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absu = normalize_url(urljoin(url, href))
        nav = is_nav(a)
        text = a.get_text(" ", strip=True)
        host = urlsplit(absu).hostname or ""
        ext = ext_of(absu)
        if ext in C.DOC_EXTS:
            ctx = a.find_previous(["h1", "h2", "h3", "h4"])
            docs.append({
                "url": absu, "anchor": text, "in_nav": nav, "ext": ext,
                "context_heading": ctx.get_text(" ", strip=True) if ctx else "",
                "external": host not in C.ALLOWED_HOSTS,
            })
        elif host in C.ALLOWED_HOSTS and ext not in C.IMG_EXTS:
            links.append({"url": absu, "anchor": text, "in_nav": nav})
    for ifr in soup.find_all(["iframe", "embed", "object"]):
        src = ifr.get("src") or ifr.get("data")
        if src and ext_of(src) in C.DOC_EXTS:
            docs.append({"url": normalize_url(urljoin(url, src)), "anchor": "(embed)", "in_nav": False,
                         "ext": ext_of(src), "context_heading": "", "external": False})
    # texte brut du contenu principal (hors navigation), utile pour les pages qui PORTENT le texte juridique
    for t in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        t.decompose()
    main = soup.find("main") or soup.find(id="content") or soup.body or soup
    text = main.get_text("\n", strip=True) if main else ""
    return {"title": title, "h1": h1.get_text(" ", strip=True) if h1 else "", "lang": lang,
            "docs": docs, "links": links, "text_len": len(text)}


def crawl(client: Client, incremental: bool = True, max_pages: int | None = None) -> dict:
    html_dir = C.CORPUS / "raw" / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    pages = read_json(C.STATE_DIR / "pages.json", {})
    rep = {"start_urls": [C.BASE + "/", C.BASE + "/wp-sitemap.xml"] + C.LEGAL_HUBS,
           "started_at": now_iso(), "sitemaps_read": [], "sitemap_failures": [],
           "robots_txt": client.robots_txt[:2000]}
    skipped, skip_examples = Counter(), {}

    def skip(reason, u):
        skipped[reason] += 1
        skip_examples.setdefault(reason, []).append(u) if len(skip_examples.get(reason, [])) < 15 else None

    sm = sitemap_urls(client, rep)
    rep["sitemap_url_count"] = len(sm)
    queue, prio = deque(), deque()
    queued = set()
    legal_depth = {}   # pages du périmètre juridique : explorées en priorité (hubs → thèmes → sous-pages)

    visited_set, prio_set = set(), set()

    def push(u, priority=False):
        u = normalize_url(u)
        if u in queued:
            if priority and u not in visited_set and u not in prio_set:
                prio.append(u); prio_set.add(u)   # promotion : déjà en file normale (ex. via sitemap)
            return
        host = urlsplit(u).hostname or ""
        if host not in C.ALLOWED_HOSTS:
            skip("external_domain", u); return
        if any(p in u for p in C.EXCLUDE_URL_PATTERNS):
            skip("excluded_pattern(feed/api/admin/preview/search)", u); return
        if not client.allowed(u):
            skip("robots_disallowed", u); return
        if ext_of(u) in C.DOC_EXTS or ext_of(u) in C.IMG_EXTS:
            return
        queued.add(u)
        if priority:
            prio.append(u); prio_set.add(u)
        else:
            queue.append(u)

    for u in C.LEGAL_HUBS:
        legal_depth[normalize_url(u)] = 0
        push(u, True)
    for u in [C.BASE + "/", C.BASE + "/ar/"] + sm:
        push(u)

    visited, failed, redirected = 0, [], []
    while queue or prio:
        if max_pages and visited >= max_pages:
            rep["stopped_early"] = f"max_pages={max_pages}"; break
        u = prio.popleft() if prio else queue.popleft()
        if u in visited_set:
            continue
        visited_set.add(u)
        prev = pages.get(u, {})
        hdr = {}
        cache = html_dir / (url_key(u) + ".html")
        if incremental and prev.get("etag") and cache.exists():
            hdr["If-None-Match"] = prev["etag"]
        elif incremental and prev.get("last_modified") and cache.exists():
            hdr["If-Modified-Since"] = prev["last_modified"]
        fresh = (incremental and prev.get("status") == 200 and cache.exists() and prev.get("checked_at")
                 and (datetime.now(timezone.utc) - datetime.fromisoformat(prev["checked_at"])).total_seconds() < REUSE_SECONDS)
        if fresh:
            class _R:  # réponse simulée : page lue dans le cache local (reprise d'un crawl interrompu)
                status_code, headers, url = 200, {"ETag": prev.get("etag"), "Last-Modified": prev.get("last_modified"), "Content-Type": "text/html"}, u
                content = cache.read_bytes()
            r = _R()
        else:
            r = client.get(u, headers=hdr)
        visited += 1
        if visited % 50 == 0:
            print(f"[crawl] {visited} visitées, {len(prio)} prioritaires, {len(queue)} en file", flush=True)
        if r is None:
            failed.append({"url": u, "error": getattr(client, "last_error", "robots/réseau")})
            print(f"[crawl] ÉCHEC réseau/robots : {u[:100]} ({str(getattr(client, 'last_error', ''))[:80]})", flush=True); continue
        if fresh:
            body = r.content
        elif r.status_code == 304 and cache.exists():
            body = cache.read_bytes(); prev["checked_at"] = now_iso()
        elif r.status_code != 200:
            failed.append({"url": u, "status": r.status_code}); print(f"[crawl] HTTP {r.status_code} : {u[:100]}", flush=True)
            pages[u] = {**prev, "status": r.status_code, "checked_at": now_iso()}; continue
        else:
            ctype = r.headers.get("Content-Type", "")
            final = normalize_url(r.url)
            if final != u:
                redirected.append({"from": u, "to": final}); push(final)
            if "html" not in ctype:
                skip(f"non_html({ctype.split(';')[0]})", u); continue
            body = r.content
            cache.write_bytes(body)
        info = parse_page(body, u)
        h = hashlib.sha256(body).hexdigest()
        info.update({"status": 200, "content_hash": h, "etag": r.headers.get("ETag", prev.get("etag")),
                     "last_modified": r.headers.get("Last-Modified", prev.get("last_modified")),
                     "checked_at": now_iso(), "first_seen": prev.get("first_seen", now_iso()),
                     "changed": bool(prev) and prev.get("content_hash") != h})
        pages[u] = info
        d = legal_depth.get(u)
        if d is None and C.LEGAL_HUB_AR_HINT in u.lower() and "/ar/" in u:
            d = legal_depth[u] = 0
        for l in info["links"]:
            if d is not None and d < C.LEGAL_BFS_DEPTH and not l["in_nav"]:
                legal_depth.setdefault(normalize_url(l["url"]), d + 1)
                push(l["url"], True)
            else:
                push(l["url"])
        if visited % 25 == 0:
            write_json(C.STATE_DIR / "pages.json", pages)

    write_json(C.STATE_DIR / "pages.json", pages)
    ok = [u for u, p in pages.items() if p.get("status") == 200]
    rep.update({
        "finished_at": now_iso(), "urls_visited": visited, "pages_ok": len(ok),
        "urls_failed": failed, "redirects": redirected[:200],
        "urls_skipped": dict(skipped), "urls_skipped_examples": skip_examples,
        "pages_changed_since_last_run": [u for u, p in pages.items() if p.get("changed")],
        "document_links_found_total": sum(len(p.get("docs", [])) for p in pages.values()),
        "http_stats": dict(client.stats),
        "note": "Pages hors sitemap découvertes par liens internes ; pages protégées/authentifiées : aucune rencontrée"
                " ou non tentée (aucun contournement).",
    })
    write_json(C.CORPUS / "reports" / "crawl_report.json", rep)
    return rep
