"""Usage : python -m boa_pipeline <étape> [options]   (voir docs/README.md)

Étapes : crawl | scope | download | build | all | report
"""
import argparse

from . import config as C
from .util import read_json, write_json


def main():
    ap = argparse.ArgumentParser(prog="boa_pipeline")
    ap.add_argument("stage", choices=["crawl", "scope", "download", "build", "status", "vectors", "all", "report"])
    ap.add_argument("--full", action="store_true", help="ignorer les caches conditionnels / forcer le retéléchargement")
    ap.add_argument("--max-pages", type=int, help="limiter le crawl (tests)")
    ap.add_argument("--delay", type=float, default=C.REQUEST_DELAY)
    ap.add_argument("--no-media-index", action="store_true")
    a = ap.parse_args()
    from .client import Client
    client = None

    def cl():
        nonlocal client
        client = client or Client(a.delay)
        return client

    if a.stage in ("crawl", "all"):
        from .crawl import crawl
        rep = crawl(cl(), incremental=not a.full, max_pages=a.max_pages)
        print("crawl:", {k: rep[k] for k in ("urls_visited", "pages_ok", "document_links_found_total")})
    if a.stage in ("scope", "all", "download", "build"):
        if a.stage in ("scope", "all"):
            from .scope import build_candidates
            r = build_candidates()
            print("scope:", r["reasons"], "pages juridiques:", r["legal_pages_count"])
    if a.stage in ("download", "all"):
        from .download import download_all, fetch_media_index
        cands = read_json(C.STATE_DIR / "candidates.json")["candidates"]
        if not a.no_media_index:
            idx = fetch_media_index(cl())
            print("médiathèque indexée:", len(idx))
        rep = download_all(cl(), cands, force=a.full)
        write_json(C.CORPUS / "reports" / "download_report.json", rep)
        print("download:", {k: len(v) for k, v in rep.items()})
    if a.stage in ("build", "all"):
        from .build import build
        recs, chunks = build()
        print("build:", len(recs), "documents,", len(chunks), "chunks")
    if a.stage in ("status", "all"):
        import subprocess, sys
        # statut juridique + séries périodiques, dérivés des relations et du texte du corpus (preuves citées ; UNKNOWN par défaut)
        r = subprocess.run([sys.executable, "-m", "agent_fr.legal_status"], cwd=str(C.ROOT))
        print("status:", "ok" if r.returncode == 0 else f"échec (code {r.returncode})")
    if a.stage in ("vectors", "all"):
        import subprocess, sys
        # encode (localement) les chunks nouveaux/modifiés pour la recherche sémantique ; ignoré si onnxruntime ou le modèle sont absents
        r = subprocess.run([sys.executable, "-m", "agent_fr.build_vectors"], cwd=str(C.ROOT))
        print("vectors:", "ok" if r.returncode == 0 else f"ignoré (code {r.returncode}) — l'agent utilisera le repli lexical")
    if a.stage in ("build", "all", "report"):
        from .report import coverage_report
        r = coverage_report()
        print("couverture:", {k: r[k] for k in ("urls_visitees", "documents_dans_perimetre", "documents_hors_perimetre")})


main()
