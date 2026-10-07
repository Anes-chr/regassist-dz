"""Étape 18 : rapport d'exhaustivité — ce qui est réellement couvert, et ce qui ne l'est pas."""
import re
from collections import Counter
from urllib.parse import unquote

from . import config as C
from .util import now_iso, read_json, write_json

LEGAL_LOOK = re.compile(r"(r[eè]glement|reglement|instruction|\bloi\b|ordonnance|d[eé]cret|lignes?[-_ ]directrices?|note[s]?[-_ ]aux|"
                        r"\bREG[-_ ]|\bLD[-_ ]|\bINS[-_ ]|نظام|تعليمة|قانون)", re.I)


def coverage_report():
    crawl = read_json(C.CORPUS / "reports" / "crawl_report.json", {})
    pages = read_json(C.STATE_DIR / "pages.json", {})
    scope = read_json(C.STATE_DIR / "candidates.json", {})
    dl = read_json(C.CORPUS / "reports" / "download_report.json", {})
    media = read_json(C.STATE_DIR / "media_index.json", {})
    ext = read_json(C.CORPUS / "reports" / "extraction_report.json", {})
    legal_pages = scope.get("legal_pages", {})

    all_doc_urls = {d["url"] for p in pages.values() for d in p.get("docs", [])}
    cand_urls = {c["url"] for c in scope.get("candidates", [])}
    unlinked = []
    for url, m in media.items():
        if url in all_doc_urls or not url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            continue
        looks = bool(LEGAL_LOOK.search(unquote(url)) or LEGAL_LOOK.search(m.get("title") or ""))
        unlinked.append({"url": url, "uploaded": m["uploaded"], "title": m["title"], "legal_looking_name": looks})
    write_json(C.CORPUS / "reports" / "unlinked_media.json", {
        "note": "Fichiers présents dans la médiathèque WordPress mais liés depuis AUCUNE page explorée. Non intégrés : "
                "rien ne prouve qu'ils sont publiés officiellement. Les 'legal_looking_name' méritent une vérification humaine.",
        "total_unlinked_files": len(unlinked),
        "legal_looking_count": sum(1 for u in unlinked if u["legal_looking_name"]),
        "files": sorted(unlinked, key=lambda u: (not u["legal_looking_name"], u["uploaded"]), reverse=False)})

    broken = []
    for pu, p in pages.items():
        if pu in legal_pages:
            for l in p.get("links", []):
                tgt = pages.get(l["url"])
                if tgt and tgt.get("status") not in (200, None) and not l["in_nav"]:
                    broken.append({"linked_from": pu, "url": l["url"], "status": tgt["status"], "anchor": l["anchor"]})
    seen, broken_u = set(), []
    for b in broken:
        if (b["url"]) not in seen:
            seen.add(b["url"]); broken_u.append(b)

    not_crawled = [u for u in legal_pages if u not in pages]
    rep = {
        "generated_at": now_iso(),
        "url_de_depart": crawl.get("start_urls"),
        "sitemaps_lus": crawl.get("sitemaps_read"),
        "urls_visitees": crawl.get("urls_visited"),
        "pages_en_succes": crawl.get("pages_ok"),
        "urls_ignorees": crawl.get("urls_skipped"),
        "pourquoi_urls_ignorees": {
            "external_domain": "hors domaine officiel (réseaux sociaux, sites tiers) — hors périmètre",
            "excluded_pattern(feed/api/admin/preview/search)": "flux, API, admin, brouillons/aperçus, recherche : pas de contenu éditorial",
            "robots_disallowed": "interdit par robots.txt (respecté)",
        },
        "urls_en_echec": crawl.get("urls_failed"),
        "pages_juridiques_identifiees": len(legal_pages),
        "pages_juridiques_non_explorees": not_crawled,
        "liens_documents_trouves_total": crawl.get("document_links_found_total"),
        "documents_uniques_trouves": len(all_doc_urls),
        "documents_dans_perimetre": len(cand_urls),
        "documents_hors_perimetre": len(scope.get("out_of_scope", [])),
        "raisons_perimetre": scope.get("reasons"),
        "documents_telecharges_nouveaux": len(dl.get("new", [])),
        "documents_inchanges": len(dl.get("unchanged", [])),
        "documents_modifies": len(dl.get("changed", [])),
        "documents_non_accessibles": dl.get("failed", []),
        "liens_casses_depuis_pages_juridiques": broken_u,
        "fichiers_mediatheque_non_lies": {"total": len(unlinked),
                                          "d_apparence_juridique": sum(1 for u in unlinked if u["legal_looking_name"]),
                                          "detail": "reports/unlinked_media.json"},
        "necessitent_intervention_humaine": {
            "documents_a_valider": ext.get("documents_suspects_ou_a_valider"),
            "documents_ocr": ext.get("documents_ocr"),
            "liste": "reports/manual_review.json, reports/ocr_required.json, reports/failed_documents.json",
        },
        "avertissement": "Ceci n'est PAS une garantie de collecte de « tous » les textes : seuls les documents liés depuis "
                         "des pages publiques explorées sont couverts ; voir liens_casses, fichiers_mediatheque_non_lies "
                         "et pages_juridiques_non_explorees.",
    }
    write_json(C.CORPUS / "reports" / "coverage_report.json", rep)
    return rep
