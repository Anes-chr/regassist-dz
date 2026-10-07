"""Vérifie en ligne (requêtes HEAD polies, robots.txt respecté, 1 requête / seconde) l'état ACTUEL des liens en échec de `reports/dead_links.json`, et si les pages du site qui les
listent les listent encore. Rien n'est modifié dans le corpus : le résultat est écrit dans `reports/dead_links_status.json` (daté).
Usage : python -m boa_pipeline.deadlinks_check"""
import json
import time

from . import config as C
from .client import Client
from .util import now_iso, read_json, write_json


def main():
    rep = C.CORPUS / "reports"
    dead = read_json(rep / "dead_links.json", [])
    pages = read_json(C.STATE_DIR / "pages.json", {})
    listed_on = {}
    for pu, pg in pages.items():
        for d in pg.get("docs", []):
            listed_on.setdefault(d["url"], []).append(pu)
    cl = Client(delay=1.0)
    out = []
    for m in dead:
        r = cl.head(m["url"])
        row = {"url": m["url"], "resolution": m["resolution"], "http_now": r.status_code if r is not None else None,
               "error": None if r is not None else getattr(cl, "last_error", "bloqué par robots.txt ou erreur réseau"),
               "still_listed_on_site_pages": listed_on.get(m["url"], [])[:5], "official_urls": []}
        for rd in m.get("resolved_documents", []):
            if rd["official_url"] in [x["url"] for x in row["official_urls"]]:
                continue
            rr = cl.head(rd["official_url"])
            row["official_urls"].append({"url": rd["official_url"], "http_now": rr.status_code if rr is not None else None})
        out.append(row)
        print(row["http_now"], m["resolution"], m["url"][-60:], [x["http_now"] for x in row["official_urls"]], flush=True)
    write_json(rep / "dead_links_status.json", {"checked_at": now_iso(), "method": "HEAD, 1 requête/s, robots.txt respecté", "n": len(out), "items": out})
    print("écrit :", rep / "dead_links_status.json")


if __name__ == "__main__":
    main()
