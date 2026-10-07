"""Étape 4 : téléchargement incrémental des documents originaux + index de la médiathèque (contrôle).

raw/<sha12>__<nom> est immuable : une nouvelle version d'un même URL crée un nouveau fichier ;
l'historique des hashes est conservé dans state/state.json.
"""
import shutil
from urllib.parse import unquote, urlsplit

from . import config as C
from .client import Client
from .util import now_iso, read_json, safe_name, sha256_file, write_json

MAGIC = {"pdf": b"%PDF", "docx": b"PK", "xlsx": b"PK", "xlsm": b"PK", "zip": b"PK"}


def fetch_media_index(client: Client) -> dict:
    """API REST publique WordPress : sert au contrôle d'exhaustivité et à la date d'upload (publication)."""
    idx, page = {}, 1
    while True:
        r = client.get(f"{C.BASE}/wp-json/wp/v2/media?per_page=100&page={page}&_fields=id,date,modified,source_url,mime_type,slug,title")
        if r is None or r.status_code != 200:
            break
        data = r.json()
        for m in data:
            idx[m["source_url"]] = {"id": m["id"], "uploaded": m["date"], "modified": m["modified"],
                                    "mime": m["mime_type"], "title": m["title"]["rendered"]}
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    write_json(C.STATE_DIR / "media_index.json", idx)
    return idx


def download_all(client: Client, cands: list, force: bool = False) -> dict:
    state = read_json(C.STATE_DIR / "state.json", {"docs": {}})
    docs = state["docs"]
    raw = C.CORPUS / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rep = {"new": [], "changed": [], "unchanged": [], "failed": [], "removed_from_site": []}
    seen = set()
    for i, c in enumerate(cands, 1):
        url = c["url"]; seen.add(url)
        prev = docs.get(url)
        if prev and not force and prev.get("raw_path") and (C.CORPUS / prev["raw_path"]).exists():
            h = client.head(url)
            same = h is not None and h.status_code == 200 and (
                (prev.get("etag") and h.headers.get("ETag") == prev["etag"]) or
                (prev.get("last_modified") and h.headers.get("Last-Modified") == prev["last_modified"]
                 and str(prev.get("size")) == h.headers.get("Content-Length", str(prev.get("size")))))
            if same:
                prev["checked_at"] = now_iso(); rep["unchanged"].append(url); continue
        r = client.get(url, stream=True)
        if r is None or r.status_code != 200:
            rep["failed"].append({"url": url, "status": None if r is None else r.status_code,
                                  "error": None if r is not None else getattr(client, "last_error", "robots/réseau"),
                                  "title": c["title"], "source_page": c["source_page"]})
            continue
        tmp = raw / "_tmp.part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        head = tmp.read_bytes()[:8]
        ext = c["ext"]
        if ext in MAGIC and not head.startswith(MAGIC[ext]):
            rep["failed"].append({"url": url, "status": 200, "error": f"contenu inattendu (début={head!r}, attendu {ext})",
                                  "title": c["title"], "source_page": c["source_page"]})
            tmp.unlink(); continue
        sha = sha256_file(tmp)
        name = safe_name(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
        rel = f"raw/{sha[:12]}__{name}"
        shutil.move(tmp, C.CORPUS / rel)
        entry = {"sha256": sha, "size": (C.CORPUS / rel).stat().st_size, "raw_path": rel,
                 "etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified"),
                 "content_type": r.headers.get("Content-Type"), "downloaded_at": now_iso(),
                 "history": (prev or {}).get("history", [])}
        if prev and prev.get("sha256") != sha:
            entry["history"] = entry["history"] + [{"sha256": prev["sha256"], "raw_path": prev["raw_path"],
                                                     "downloaded_at": prev["downloaded_at"]}]
            rep["changed"].append(url)
        elif prev:
            rep["unchanged"].append(url)
        else:
            rep["new"].append(url)
        docs[url] = entry
        if i % 25 == 0:
            print(f"[download] {i}/{len(cands)}", flush=True); write_json(C.STATE_DIR / "state.json", state)
    rep["removed_from_site"] = [u for u in docs if u not in seen and not docs[u].get("removed")]
    for u in rep["removed_from_site"]:
        docs[u]["removed"] = True  # conservé localement : on ne supprime jamais une source archivée
    write_json(C.STATE_DIR / "state.json", state)
    return rep
