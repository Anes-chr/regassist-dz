"""Orchestration : extraction → nettoyage → structure → métadonnées → dédup → relations → qualité → chunks → rapports."""
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import config as C
from .chunk import make_chunks
from .classify import (CORR_RE, TYPE_LABEL, detect_language, detect_type, parse_date, parse_number, clean_label)
from .clean import clean_pages
from .dedup import dedup_files, dedup_text_and_versions
from .deadlinks import attach_to_documents, reconcile
from .extract import extract
from .ocr_check import annotate_document
from .quality import check_document
from .relations import assign_ids, link_documents, num_key
from .structure import nest, parse_structure
from .util import now_iso, read_json, sha256_text, write_json

PIPELINE_VERSION = "1.1"
ISSUER_BOA = {"REG", "INS", "NOT", "LD", "DCS", "CIR", "AVI", "COM"}
TEXT_HEAD_RE = re.compile(r"(r[èe]glement|instruction|loi|ordonnance|d[ée]cret|d[ée]cision|note|circulaire|lignes?\s+directrices?)"
                          r"\s+(?:\w+\s+)?n\s*[°ºo]?\s*[°º]?\s*[:.]?\s*\d{1,4}\s*[-/–]\s*\d{1,4}", re.I)


def extract_cached(raw_path: Path, sha: str, ext: str, lang_hint: str) -> dict:
    cdir = C.STATE_DIR / "extract_cache"
    cdir.mkdir(parents=True, exist_ok=True)
    cf = cdir / f"{sha[:16]}_{lang_hint}_v{PIPELINE_VERSION}.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    res = extract(raw_path, ext, lang_hint)
    write_json(cf, res)
    return res


TYPE_START = re.compile(r"^\s*(r[èe]glement|instruction|loi|ordonnance|d[ée]cret|d[ée]cision|note|circulaire|lignes?\s+directrices?|"
                        r"نظام|تعليمة|قانون|أمر|مرسوم|مقرر|قرار)(?!\w)", re.I)


def title_from_text(lines: list[str]) -> str | None:
    """Intitulé tel qu'imprimé dans le document : bloc de lignes commençant par « Règlement/Instruction n° … »,
    jusqu'à la première ligne vide (ou 8 lignes)."""
    start = next((i for i, l in enumerate(lines[:30]) if TYPE_START.match(l) and re.search(r"\d", l)), None)
    if start is None:
        return None
    blk = []
    for l in lines[start:start + 8]:
        if not l.strip():
            break
        blk.append(l.strip())
    t = re.sub(r"\s+", " ", " ".join(blk)).strip()
    # l'intitulé n'est pas toujours séparé du corps par une ligne vide : on coupe aux amorces habituelles du corps
    t = re.split(r"\s(?=(?:Article|ARTICLE)\s+(?:1|premier|1er)|Le Gouverneur|LE GOUVERNEUR|Vu(?!\w)|En application|CHAPITRE|TITRE)", t, maxsplit=1)[0]
    return t[:600] or None


def repair_header(t: str) -> str:
    """Espaces parasites dans le numéro imprimé (« N°0 2-2022 », « 03-201 9 ») : réparés pour l'analyse seulement."""
    t = re.sub(r"(N\s*°\s*)0\s+(\d)", r"\g<1>0\g<2>", t)
    return re.sub(r"([-/]\s*(?:19|20)\d)\s+(\d)(?!\d)", r"\g<1>\g<2>", t)


def reconcile_with_document(rec: dict, doc_title: str | None):
    """L'en-tête imprimé dans le document prime sur le libellé du site ; le libellé est conservé et toute
    divergence est signalée (jamais corrigée silencieusement). Non appliqué aux textes issus d'OCR."""
    if not doc_title:
        return
    doc_title = repair_header(doc_title)[:300]
    dn = parse_number(doc_title)
    dd, draw = parse_date(doc_title)
    if dn:
        if rec["number"] and num_key(dn) != num_key(rec["number"]):
            rec["quality_flags"].append("incoherence_libelle_vs_document:numero")
            rec["label_number"] = rec["number"]
        elif rec["number"] and dn != rec["number"]:
            rec["label_number"] = rec["number"]   # même numéro, format différent (ex. 2022-01 vs 22-01)
        rec["number"], rec["number_source"] = dn, "en-tête du document"
    if dd:
        if rec["date"] and rec["date"] != dd:
            rec["quality_flags"].append("incoherence_libelle_vs_document:date")
            rec["label_date"] = rec["date"]
        rec["date"], rec["date_raw"], rec["date_source"] = dd, draw, "en-tête du document"


def fill_from_text(rec: dict, first_text: str):
    """Complète numéro/date/type absents du libellé à partir de l'en-tête du document (avec traçabilité)."""
    head = first_text[:3000]
    own = None
    if rec.get("number"):                                    # on ancre sur le numéro PROPRE du texte (sinon on tombait sur un texte cité : « instruction n°08-16 du 1er septembre 2016 »)
        parts = [x for x in re.split(r"[-–/]", str(rec["number"])) if x]
        if len(parts) >= 2:
            own = re.search(r"(?<!\w)n\s*[°º]?\s*" + r"\s*[-–/]\s*".join(re.escape(x) for x in parts[:3]), head, re.I)
    m = TEXT_HEAD_RE.search(head)
    if own:
        window = head[max(0, own.start() - 60): own.start() + 400]
    elif m and rec.get("number") and sorted(num_key(parse_number(m.group(0)) or "") or ()) != sorted(num_key(rec["number"]) or ()):
        window = ""        # la première référence « type n° … » du texte n'est PAS ce texte (c'est un texte cité) : pas de date plutôt que la date d'un autre texte (NOT-02-24 : 2016 au lieu de 2024)
    else:
        window = first_text[m.start(): m.start() + 400] if m else first_text[:800]
    if not rec["number"]:
        n = parse_number(window)
        if n:
            rec["number"], rec["number_source"] = n, "texte_du_document"
    if not rec["date"]:
        iso, raw = parse_date(window)
        if iso:
            rec["date"], rec["date_raw"], rec["date_source"] = iso, raw, "texte_du_document"
    if rec["type_code"] == "OTH" and m:
        t = detect_type(m.group(1))
        if t:
            rec["type_code"], rec["document_type"], rec["type_source"] = t, TYPE_LABEL[t], "texte_du_document"


def hijri_from(text: str):
    m = re.search(r"(\d{1,2}\s+(?:[A-Za-zéû' ]+)\s+14\d\d)\s+correspondant", text or "")
    return m.group(1).strip() if m else None


def build(only_urls: set | None = None):
    cands = read_json(C.STATE_DIR / "candidates.json")["candidates"]
    state = read_json(C.STATE_DIR / "state.json", {"docs": {}})["docs"]
    media = read_json(C.STATE_DIR / "media_index.json", {})
    recs, failed = [], []
    media_by_name = {}
    for u, mm in media.items():
        media_by_name.setdefault(u.rsplit("/", 1)[-1], []).append((u, mm))
    for i, c in enumerate(cands, 1):
        st = state.get(c["url"])
        if not st or st.get("removed") and not (C.CORPUS / st["raw_path"]).exists():
            failed.append({"url": c["url"], "title": c["title"], "stage": "download", "reason": "non téléchargé"}); continue
        if only_urls and c["url"] not in only_urls:
            continue
        raw = C.CORPUS / st["raw_path"]
        ex = extract_cached(raw, st["sha256"], c["ext"], c["language_hint"])
        pages_clean, clog = clean_pages(ex["pages"]) if ex["pages"] else ([], [])
        for p_raw, p_c in zip(ex["pages"], pages_clean):
            p_raw["chars"] = len(p_raw["text"].strip())
        full = "\n".join(f"[[PAGE {p['page']}]]\n" + "\n".join(p["lines"]) for p in pages_clean)
        plain = "\n".join("\n".join(p["lines"]) for p in pages_clean)
        lang = c["language_hint"]
        det = detect_language(plain)
        if det in ("fr", "ar", "mixed"):
            lang = det
        if lang == "und":
            lang = "fr" if re.search(r"[A-Za-z]{4}", c["title"]) else "und"
        sinfo = parse_structure(pages_clean, "ar" if lang == "ar" else "fr") if pages_clean else \
            {"structure_detected": False, "units": [], "article_count": 0, "annex_count": 0}
        path_year = re.search(r"/stoodroa/(\d{4})/(\d{2})/", c["url"])
        m = media.get(c["url"])
        alts = [{"url": u, "uploaded": mm["uploaded"]} for u, mm in media_by_name.get(c["url"].rsplit("/", 1)[-1], [])
                if u != c["url"]]
        rec = {
            "document_id": None, "work_id": None,
            "title": c["title"], "document_type": c["document_type"], "type_code": c["type_code"],
            "type_source": c["type_source"], "number": c["number"], "number_source": "libelle" if c["number"] else None,
            "date": c["date"], "date_raw": c["date_raw"], "date_source": "libelle" if c["date"] else None,
            "publication_date": (m["uploaded"][:10] if m else (f"{path_year.group(1)}-{path_year.group(2)}" if path_year else None)),
            "publication_date_source": ("wp_media_upload_date" if m else ("url_path(mois)" if path_year else None)),
            "media_library_alternates": alts,
            "publication_note": "Date de mise en ligne sur le site (≠ date de signature, ≠ publication au Journal officiel).",
            "issuer": "Banque d'Algérie" if c["type_code"] in ISSUER_BOA else None,
            "issuer_note": None if c["type_code"] in ISSUER_BOA else "Émetteur non établi par la source (publié sur le site de la Banque d'Algérie).",
            "published_on": "Banque d'Algérie (site officiel)",
            "language": lang, "category": c["category"], "subcategory": c["subcategory"],
            "source_url": c["source_page"], "document_url": c["url"], "format": c["ext"],
            "file_hash": st["sha256"], "file_size": st["size"], "raw_path": st["raw_path"],
            "retrieved_at": st["downloaded_at"], "scope_reason": c["scope_reason"],
            "extraction_method": ex["method"] if ex["pages"] else "failed",
            "ocr_required": ex.get("ocr_pages", 0) > 0 or ex["method"] in ("ocr", "mixed"),
            "page_count": ex.get("page_count"), "url_hash": sha256_text(c["url"]),
            "all_source_urls": c["all_source_pages"], "pdf_metadata": ex.get("metadata", {}),
            "hijri_date_raw": hijri_from(plain[:3000]),
            "extraction": {"method": ex["method"], "page_count": ex.get("page_count"), "errors": ex.get("errors", []),
                           "pages": [{"page": p["page"], "method": p["method"], "chars": p.get("chars", 0),
                                      "ocr_confidence": p.get("ocr_confidence")} for p in ex["pages"]],
                           "cleaning_removed": clog},
            "structure_info": {k: sinfo[k] for k in ("structure_detected", "article_count", "annex_count")},
            "_units": sinfo["units"], "_full_text": plain, "_marked_text": full, "_tables": [
                {"page": p["page"], "tables": p["tables"]} for p in pages_clean if p.get("tables")],
            "quality_flags": [],
        }
        first = "\n".join(pages_clean[0]["lines"]) if pages_clean else ""
        rec["title_document"] = title_from_text(pages_clean[0]["lines"]) if pages_clean else None
        if rec["extraction_method"] == "pdf_text":
            reconcile_with_document(rec, rec["title_document"])
        fill_from_text(rec, plain[:4000])
        if not rec["title"] or len(rec["title"]) < 8:
            rec["title"] = rec["title_document"] or unquote(urlsplit(c["url"]).path.rsplit("/", 1)[-1])
        recs.append(rec)
        if i % 20 == 0:
            print(f"[build] {i}/{len(cands)}", flush=True)

    recs, dup_rep = dedup_files(recs)
    assign_ids(recs)
    dup_rep = dedup_text_and_versions(recs, dup_rep) or dup_rep
    link_documents(recs)
    dl = read_json(C.CORPUS / "reports" / "download_report.json", {})
    dead = reconcile(list(failed) + [dict(x, stage="download") for x in dl.get("failed", [])], recs, {c["url"]: c for c in cands})   # liens morts : diagnostic sans deviner d'URL
    attach_to_documents(dead, recs)
    fr_of = {}
    for d in recs:
        if d["language"] == "fr" and "~" not in d["document_id"]:
            fr_of.setdefault(d["work_id"], d)
    for d in recs:                                             # OCR_UNCERTAIN : valeurs numériques arabes suspectes (comparées au texte français du même texte juridique ; jamais corrigées)
        if d["language"] == "ar" and d["extraction_method"] in ("ocr", "mixed"):
            d["ocr_numeric_check"] = annotate_document(d, fr_of.get(d["work_id"]))
            if d["ocr_numeric_check"]["units_flagged"]:
                d["quality_flags"].append(f"ocr_uncertain_numbers:{d['ocr_numeric_check']['units_flagged']}")
    qrep = {}
    for d in recs:
        qrep[d["document_id"]] = check_document(d)
    chunks = []
    for d in recs:
        chunks += make_chunks(d, d["_units"])
    write_outputs(recs, chunks, dup_rep, qrep, failed, dead)
    return recs, chunks


def write_outputs(recs, chunks, dup_rep, qrep, failed_dl, dead=None):
    out = C.CORPUS
    LANGS = ("fr", "ar", "und")   # textes séparés par langue ; « und » = langue non déterminée (à vérifier)
    for sub in ("documents", "extracted"):
        for lg in LANGS:
            (out / sub / lg).mkdir(parents=True, exist_ok=True)
            for f in list((out / sub / lg).glob("*.json")) + list((out / sub / lg).glob("*.txt")):
                f.unlink()
        for f in list((out / sub).glob("*.json")) + list((out / sub).glob("*.txt")):   # anciennes sorties à plat
            f.unlink()
    for sub in ("chunks", "metadata", "reports"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    lang_of = lambda d: d["language"] if d["language"] in ("fr", "ar") else "und"
    meta = []
    for d in recs:
        doc = {k: v for k, v in d.items() if not k.startswith("_")}
        doc["structure"] = nest(d["_units"])
        doc["units"] = [{**{k: u[k] for k in ("kind", "label", "number", "heading", "context", "annexe", "page_start", "page_end")},
                         "text": u["text"], "paragraphs": u["paragraphs"]} for u in d["_units"]]
        doc["tables_markdown"] = d["_tables"]
        doc["quality"] = qrep[d["document_id"]]
        doc["pipeline_version"] = PIPELINE_VERSION
        lg = lang_of(d)
        doc["extracted_text_path"] = f"extracted/{lg}/{d['document_id']}.txt"
        write_json(out / "documents" / lg / f"{d['document_id']}.json", doc)
        (out / "extracted" / lg / f"{d['document_id']}.txt").write_text(d["_marked_text"], encoding="utf-8")
        m = {k: v for k, v in doc.items() if k not in ("structure", "units", "tables_markdown", "extraction", "pdf_metadata")}
        m["extraction"] = {"method": d["extraction"]["method"], "errors": d["extraction"]["errors"]}
        meta.append(m)
    write_json(out / "metadata" / "documents.json", meta)
    for lg in LANGS:
        write_json(out / "metadata" / f"documents_{lg}.json",
                   [m for m in meta if lang_of(m) == lg])
    for f in (out / "chunks").glob("chunks*.jsonl"):
        f.unlink()
    handles = {lg: open(out / "chunks" / f"chunks_{lg}.jsonl", "w", encoding="utf-8") for lg in LANGS}
    with open(out / "chunks" / "chunks.jsonl", "w", encoding="utf-8") as f:   # fichier combiné (compatibilité)
        for c in chunks:
            line = json.dumps(c, ensure_ascii=False) + "\n"
            f.write(line)
            handles[lang_of(c)].write(line)
    for h in handles.values():
        h.close()
    # --- rapports
    write_json(out / "reports" / "duplicates.json", dup_rep)
    dead = dead or []
    write_json(out / "reports" / "dead_links.json", dead)                      # TOUS les liens en échec, dédoublonnés, avec leur résolution (MOVED_OFFICIAL / BROKEN_SOURCE)
    failed = [
        {"document_id": d["document_id"], "url": d["document_url"], "title": d["title"], "stage": "extraction",
         "reasons": qrep[d["document_id"]]["flags"], "errors": d["extraction"]["errors"]}
        for d in recs if qrep[d["document_id"]]["severity"] == "failed"]
    failed += [{"url": m["url"], "title": m["title"], "stage": "+".join(m["stages"]), "reason": "BROKEN_SOURCE", "note": m["note"]} for m in dead if m["resolution"] == "BROKEN_SOURCE"]
    write_json(out / "reports" / "failed_documents.json", failed)              # uniquement les vrais échecs : un lien déplacé dont le fichier est dans le corpus n'est pas un échec
    review = [{"document_id": d["document_id"], "title": d["title"], "document_url": d["document_url"],
               "severity": qrep[d["document_id"]]["severity"], "reasons": qrep[d["document_id"]]["flags"],
               "details": qrep[d["document_id"]]["details"]} for d in recs if d["needs_manual_review"]]
    lang_by_id = {d["document_id"]: lang_of(d) for d in recs}
    for r in review:
        r["language"] = lang_by_id[r["document_id"]]
    write_json(out / "reports" / "manual_review.json", review)
    for lg in LANGS:
        write_json(out / "reports" / f"manual_review_{lg}.json", [r for r in review if r["language"] == lg])
    ocr = [{"document_id": d["document_id"], "title": d["title"], "document_url": d["document_url"],
            "ocr_pages": qrep[d["document_id"]]["details"].get("ocr_pages"),
            "mean_confidence": qrep[d["document_id"]]["details"].get("ocr_mean_confidence"),
            "note": "Texte issu de l'OCR : non fiable à 100 %, vérification humaine requise."}
           for d in recs if d["ocr_required"]]
    for r in ocr:
        r["language"] = lang_by_id[r["document_id"]]
    write_json(out / "reports" / "ocr_required.json", ocr)
    for lg in LANGS:
        write_json(out / "reports" / f"ocr_required_{lg}.json", [r for r in ocr if r["language"] == lg])
    pdfs = [d for d in recs if d["format"] == "pdf"]
    crawl = read_json(out / "reports" / "crawl_report.json", {})
    scope = read_json(C.STATE_DIR / "candidates.json", {})
    ext_rep = {
        "generated_at": now_iso(), "pipeline_version": PIPELINE_VERSION,
        "pages_explorees": crawl.get("urls_visited"), "documents_trouves_total_liens": crawl.get("document_links_found_total"),
        "documents_candidats_dans_perimetre": len(scope.get("candidates", [])),
        "documents_hors_perimetre": len(scope.get("out_of_scope", [])),
        "documents_dans_corpus": len(recs),
        "textes_juridiques_normatifs": sum(1 for d in recs if d["type_code"] in ("LOI", "ORD", "DEC", "REG", "INS", "DCS", "CIR", "LD", "NOT")),
        "pdf_total": len(pdfs),
        "pdf_textuels": sum(1 for d in pdfs if d["extraction"]["method"] == "pdf_text"),
        "pdf_mixtes_texte_et_ocr": sum(1 for d in pdfs if d["extraction"]["method"] == "mixed"),
        "pdf_necessitant_ocr": sum(1 for d in pdfs if d["ocr_required"]),
        "documents_ocr": sum(1 for d in recs if d["ocr_required"]),
        "documents_echoues": len(failed),
        "liens_en_echec_uniques": len(dead), "liens_deplaces_officiels": sum(1 for m in dead if m["resolution"] == "MOVED_OFFICIAL"),
        "sources_cassees": sum(1 for m in dead if m["resolution"] == "BROKEN_SOURCE"),
        "doublons_fichiers_identiques": len(dup_rep.get("identical_files", [])),
        "doublons_texte_identique": len(dup_rep.get("identical_text_different_files", [])),
        "documents_metadonnees_incompletes": sum(1 for d in recs if d.get("missing_metadata")),
        "articles_extraits": sum(d["structure_info"]["article_count"] for d in recs),
        "documents_avec_structure_detectee": sum(1 for d in recs if d["structure_info"]["structure_detected"]),
        "chunks": len(chunks),
        "par_langue_documents": dict(Counter(lang_of(d) for d in recs)),
        "par_langue_chunks": dict(Counter(c["language"] if c["language"] in ("fr", "ar") else "und" for c in chunks)),
        "par_langue_articles": {lg: sum(d["structure_info"]["article_count"] for d in recs if lang_of(d) == lg) for lg in LANGS},
        "ocr_par_langue": {lg: sum(1 for d in recs if lang_of(d) == lg and d["ocr_required"]) for lg in LANGS},
        "documents_suspects_ou_a_valider": len(review),
        "documents_statut_a_verifier": sum(1 for d in recs if d["status"] == "STATUT À VÉRIFIER"),
        "documents_abroges_prouves": sum(1 for d in recs if d["status"] == "abrogé"),
        "par_type": dict(Counter(d["document_type"] for d in recs)),
        "par_langue": dict(Counter(d["language"] for d in recs)),
        "flags_frequents": Counter(f.split(":")[0] for d in recs for f in d["quality_flags"]).most_common(20),
        "incomplets_probables": [d["document_id"] for d in recs if "texte_anormalement_court" in d["quality_flags"]
                                 or any(f.startswith("numerotation:articles_manquants") for f in d["quality_flags"])],
        "mal_extraits_probables": [d["document_id"] for d in recs if set(d["quality_flags"]) & {
            "taux_anormal_caracteres_non_alphabetiques", "caracteres_illisibles", "ocr_faible_confiance", "pages_sans_texte"}],
    }
    write_json(out / "reports" / "extraction_report.json", ext_rep)
