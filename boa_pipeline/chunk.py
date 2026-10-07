"""Étape 10-11 : chunking sémantique (Article → alinéa) avec contexte et citations.

Un article = un chunk, tant qu'il tient dans CHUNK_MAX_CHARS. Sinon découpe aux limites de paragraphes (alinéas),
jamais au milieu d'une phrase sauf paragraphe unique démesuré. `text` = texte fidèle ; `text_with_context` = texte
préfixé de l'en-tête (document, hiérarchie) pour l'embedding / la lecture autonome.
"""
import re

from . import config as C


def _prefix(doc: dict, u: dict) -> str:
    head = f"{doc['document_type'].capitalize()}"
    if doc.get("number"):
        head += f" n° {doc['number']}"
    if doc.get("date"):
        head += f" du {doc['date']}"
    head += f" — {doc['title']}"
    path = []
    ctx = u.get("context") or {}
    for k in ("titre", "chapitre", "section", "sous_section"):
        if ctx.get(k):
            path.append(ctx[k]["label"] + (f" ({ctx[k]['heading']})" if ctx[k].get("heading") else ""))
    if u.get("annexe") and u["kind"] != "annexe":
        a = u["annexe"]
        path.append(a["label"] + (f" ({a['heading']})" if a.get("heading") else ""))
    if u["kind"] == "article":
        path.append(u["label"])
    elif u["kind"] == "annexe":
        path.append(u["label"] + (f" ({u['heading']})" if u.get("heading") else ""))
    elif u["kind"] == "preamble":
        path.append("Préambule")
    return head + ("\n" + " > ".join(path) if path else "")


def _split_long(text: str, limit: int) -> list[str]:
    sents = re.split(r"(?<=[.;:!?])\s+", text)
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def unique_chunk_id(used: set, base: str, ui: int) -> str:
    """Identifiant STABLE (même document, même structure -> même identifiant), DÉTERMINISTE et UNIQUE dans le document.
    Cause des 76 doublons de la phase 3 : plusieurs unités du même document portent le même libellé (additif qui recommence à l'article 1, annexes de même numéro) et la
    détection ne comparait qu'avec les 3 derniers chunks. Règle : le premier chunk garde l'identifiant historique ; un suivant reçoit `::u<indice de l'unité>`
    (indice = position de l'unité dans le document) ; si cela ne suffit pas (même unité découpée en pièces de même rang), `::d<n>`."""
    cid = base
    if cid in used:
        cid = f"{base}::u{ui}"
    n = 2
    while cid in used:
        cid = f"{base}::u{ui}::d{n}"
        n += 1
    used.add(cid)
    return cid


def make_chunks(doc: dict, units: list) -> list[dict]:
    chunks = []
    used: set = set()
    for ui, u in enumerate(units):
        paras = [p for p in u["paragraphs"] if p["text"].strip()]
        if not paras:
            continue
        pieces, cur = [], []
        size = 0
        for p in paras:
            pl = len(p["text"])
            if pl > C.CHUNK_MAX_CHARS:  # paragraphe démesuré (OCR sans ponctuation, tableau) : découpe par phrases
                if cur:
                    pieces.append(cur); cur, size = [], 0
                for part in _split_long(p["text"], C.CHUNK_MAX_CHARS):
                    pieces.append([{"text": part, "page_start": p["page_start"], "page_end": p["page_end"]}])
                continue
            if cur and size + pl > C.CHUNK_MAX_CHARS:
                pieces.append(cur); cur, size = [], 0
            cur.append(p); size += pl + 1
        if cur:
            pieces.append(cur)
        prefix = _prefix(doc, u)
        for pi, piece in enumerate(pieces, 1):
            text = "\n".join(p["text"] for p in piece)
            ctx = u.get("context") or {}
            ocr = doc["extraction_method"] in ("ocr", "mixed")
            art = u["number"] if u["kind"] == "article" else None
            cid = f"{doc['document_id']}::{u['kind']}-{u['number'] or ui}"
            if len(pieces) > 1:
                cid += f"::p{pi}"
            cid = unique_chunk_id(used, cid, ui)                  # numérotation d'article / d'annexe dupliquée dans le texte source
            chunks.append({
                "chunk_id": cid,
                "document_id": doc["document_id"], "work_id": doc["work_id"],
                "title": doc["title"], "document_type": doc["document_type"], "number": doc["number"],
                "date": doc["date"], "publication_date": doc.get("publication_date"),
                "language": doc["language"], "status": doc["status"],
                "titre": (ctx.get("titre") or {}).get("label"),
                "chapter": (ctx.get("chapitre") or {}).get("label"),
                "chapter_heading": (ctx.get("chapitre") or {}).get("heading"),
                "section": (ctx.get("section") or {}).get("label"),
                "annexe": (u.get("annexe") or {}).get("label") if u["kind"] != "annexe" else u["label"],
                "article": art, "article_label": u["label"] if u["kind"] == "article" else None,
                "unit_kind": u["kind"], "part": f"{pi}/{len(pieces)}" if len(pieces) > 1 else None,
                "source_url": doc["source_url"], "document_url": doc["document_url"],
                "page_number": piece[0]["page_start"], "page_end": piece[-1]["page_end"],
                "document_title": doc["title"], "document_date": doc["date"],
                "extraction_method": "ocr" if ocr else doc["extraction_method"],
                "needs_review": bool(doc["needs_manual_review"]),
                "text": text, "text_with_context": f"{prefix}\n{text}", "char_count": len(text),
            })
            if u.get("ocr_uncertain"):                                  # valeur numérique suspecte (OCR arabe) : signalée, JAMAIS corrigée ; le texte reste celui de l'OCR
                chunks[-1]["ocr_uncertain"] = True
                chunks[-1]["ocr_uncertain_tokens"] = u["ocr_uncertain"]
            if u.get("ocr_numeric_notes"):
                chunks[-1]["ocr_numeric_notes"] = u["ocr_numeric_notes"]
    return chunks
