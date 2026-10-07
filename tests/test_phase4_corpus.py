"""Phase 4 — corrections objectives du corpus : identifiants de chunks uniques, numéros d'annexe, dates arabes, rattachement FR/AR.
Lancer : python tests/test_phase4_corpus.py   (sans réseau)"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boa_pipeline import relations
from boa_pipeline.chunk import make_chunks, unique_chunk_id
from boa_pipeline.classify import parse_date, parse_day_month_ar
from boa_pipeline.clean import clean_pages
from boa_pipeline.relations import assign_ids, pair_twins
from boa_pipeline.structure import parse_structure

ROOT = Path(__file__).resolve().parent.parent


def _doc(**kw):
    d = {"document_id": "X-01-20.fr", "work_id": "X-01-20", "title": "Règlement n° 01-20", "document_type": "règlement", "number": "01-20", "date": "2020-01-01",
         "publication_date": None, "language": "fr", "status": "STATUT À VÉRIFIER", "source_url": "u", "document_url": "u", "extraction_method": "pdf_text", "needs_manual_review": False}
    d.update(kw)
    return d


def _unit(kind, number, text, label=None):
    return {"kind": kind, "number": number, "label": label or (f"Article {number}" if kind == "article" else f"Annexe {number or ''}".strip()), "heading": None,
            "context": {}, "annexe": None, "paragraphs": [{"text": text, "page_start": 1, "page_end": 1}]}


def test_chunk_ids_are_unique_stable_and_deterministic():
    """Cause des 76 doublons de la phase 3 : un additif recommence à l'article 1 et plusieurs annexes portent le même libellé, mais seuls les 3 derniers chunks étaient comparés."""
    units = [_unit("article", str(i), f"texte principal {i}") for i in range(1, 6)] + [_unit("annexe", "N", "annexe A"), _unit("annexe", "N", "annexe B")] + \
            [_unit("article", str(i), f"additif {i}") for i in range(1, 6)] + [_unit("annexe", "N", "annexe C")]
    a = [c["chunk_id"] for c in make_chunks(_doc(), units)]
    b = [c["chunk_id"] for c in make_chunks(_doc(), units)]
    assert len(a) == len(set(a)) == len(units)                                   # unique
    assert a == b                                                                # déterministe et stable
    assert a[0] == "X-01-20.fr::article-1" and a[5] == "X-01-20.fr::annexe-N"    # le premier garde l'identifiant historique
    assert a[7] == "X-01-20.fr::article-1::u7"                                   # le suivant : indice de l'unité (position dans le document)


def test_unique_chunk_id_never_returns_a_used_identifier():
    used = {"D::article-1", "D::article-1::u4"}
    cid = unique_chunk_id(used, "D::article-1", 4)
    assert cid not in {"D::article-1", "D::article-1::u4"} and cid in used


def test_annex_number_is_neither_the_letter_N_nor_the_arabic_word_for_number():
    fr = parse_structure(clean_pages([{"page": 1, "text": "ANNEXE N° 1\nListe des rubriques\nContenu un.\nANNEXE N° 2\nAutre liste\nContenu deux.", "method": "pdf_text"}])[0], "fr")
    assert [u["number"] for u in fr["units"] if u["kind"] == "annexe"] == ["1", "2"]
    ar = parse_structure(clean_pages([{"page": 1, "text": "الملحق رقم 1\nجدول\nمحتوى.\nالملحق رقم 2\nجدول آخر\nمحتوى.", "method": "pdf_text"}])[0], "ar")
    assert [u["number"] for u in ar["units"] if u["kind"] == "annexe"] == ["1", "2"]


def test_arabic_article_header_with_glued_digit_or_vowel_marks_is_detected_and_lookalike_words_are_not():
    """Phase 3 : « المادة8. — » (chiffre collé) n'était pas un en-tête : 41 textes arabes, dont REG-20-01 (18 articles) et REG-26-03 (15), sans article détecté."""
    from boa_pipeline.structure import classify_line
    assert classify_line("المادة8. — تحدد كيفيات تطبيق هذا النظام", "ar")[:2] == ("article", "8")
    assert classify_line("المادَة8. —", "ar")[:2] == ("article", "8") and classify_line("المادّة 9. — تُلغى كل الأحكام", "ar")[:2] == ("article", "9")
    assert classify_line("المادة الأولى : الهدف", "ar")[:2] == ("article", "1")
    assert classify_line("المادلة 4 نص", "ar") is None and classify_line("المواد 5 و 6", "ar") is None
    txt = "المادة1. — الغرض\nنص أول.\nالمادة2. — التعريف\nنص ثان.\nالمادة3. — الدخول حيز التنفيذ"
    st = parse_structure(clean_pages([{"page": 1, "text": txt, "method": "pdf_text"}])[0], "ar")
    assert [u["number"] for u in st["units"] if u["kind"] == "article"] == ["1", "2", "3"]


def test_arabic_label_dates_with_month_glued_to_day_or_year_and_first_of_month():
    assert parse_date("نظام رقم 08-04 المؤرخ في 23 ديسمبر2008، يتعلق بالحد")[0] == "2008-12-23"
    assert parse_date("نظام رقم 91-02 المؤرخ في 20 فبراير1991، يحدد")[0] == "1991-02-20"
    assert parse_date("نظام رقم 91-09 المؤرخ في 14غشت 1991، الذي")[0] == "1991-08-14"
    assert parse_date("نظام رقم 25-03 مؤرخ في 15 شوال عام 1446 الموافق 14أفريل سنة 2025 يتعلق")[0] == "2025-04-14"
    assert parse_date("تعليمة رقم 08-2021 المؤرخة في الفاتح جويلية 2021، تعدل وتتمم التعليمة رقم 05-2020 المؤرخة في 29 أفريل 2020")[0] == "2021-07-01"


def test_arabic_date_of_a_cited_text_is_never_taken_as_the_documents_own_date():
    t = "نظام رقم 92-10 المؤرخ في 17 نوفمبر يعدل ويتمم النظام رقم 91-06 المؤرخ في 16 مايو 1991"
    assert parse_date(t)[0] is None                                              # année absente : pas de date plutôt qu'une date fausse (celle du texte cité)
    assert parse_day_month_ar(t) == (17, 11)                                     # jour et mois seulement, utilisables comme INDICE de rattachement (jamais comme date)


def _pair(fr_kw, ar_kw, extra_fr=()):
    fr = {"type_code": "REG", "number": "2004-04", "date": "2004-07-19", "language": "fr", "title": "Règlement n°2004-04", "document_url": "fr1", "url_hash": "aa" * 8}
    ar = {"type_code": "REG", "number": "04-04", "date": None, "language": "ar", "title": "نظام رقم 04-04 المؤرخ في 19 يوليو، يحدد النسبة", "document_url": "ar1", "url_hash": "bb" * 8}
    fr.update(fr_kw)
    ar.update(ar_kw)
    docs = [fr, ar] + [dict(fr, document_url=f"fr{i}", url_hash=f"{i:02d}" * 8, **e) for i, e in enumerate(extra_fr, 2)]
    assign_ids(docs)
    return docs


def test_twin_pairing_by_day_month_requires_unique_fr_text_and_year_in_the_number():
    fr, ar = _pair({}, {})[:2]
    assert fr["work_id"] == ar["work_id"] and ar["twin_rule"] == "R-TWIN-JOURMOIS" and ar["date"] == "2004-07-19"
    assert ar["date_source"].startswith("jumeau_FR") and ar["date_before_pairing"] is None                 # provenance conservée


def test_twin_pairing_is_refused_when_day_month_differs_or_year_not_in_number_or_two_fr_candidates():
    for fr_kw, ar_kw, extra in (({"date": "2004-07-20"}, {}, ()),                                                       # jour différent
                                ({"number": "2004-04", "date": "2007-07-19"}, {}, ()),                                  # année absente du numéro
                                ({}, {}, ({"date": "2004-09-01"},))):                                                   # deux textes FR de même numéro : ambigu
        docs = _pair(fr_kw, ar_kw, extra)
        assert docs[0]["work_id"] != docs[1]["work_id"] and not docs[1].get("twin_rule")


def test_date_conflict_is_flagged_never_resolved_automatically():
    fr, ar = _pair({"date": "1990-07-04", "number": "90-01"}, {"date": "1990-06-04", "number": "90-01", "title": "نظام رقم 90-01 المؤرخ في 4 يونيو 1990"})[:2]
    assert fr["work_id"] != ar["work_id"] and ar["twin_status"].startswith("CONFLIT_DE_DATE")


def test_twin_override_is_applied_only_when_confirmed_by_a_human():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "ov.json"
        old = relations.OVERRIDES_FILE
        try:
            relations.OVERRIDES_FILE = f
            f.write_text(json.dumps({"confirmed": [], "proposals": [{"ar_url": "ar1", "fr_url": "fr1", "confirmed_by": None}]}), encoding="utf-8")
            fr, ar = _pair({"date": "1990-07-04", "number": "90-01"}, {"date": "1990-06-04", "number": "90-01"})[:2]
            assert fr["work_id"] != ar["work_id"]                                                                        # proposition non confirmée : jamais appliquée
            f.write_text(json.dumps({"confirmed": [{"ar_url": "ar1", "fr_url": "fr1", "confirmed_by": "juriste test"}]}), encoding="utf-8")
            fr, ar = _pair({"date": "1990-07-04", "number": "90-01"}, {"date": "1990-06-04", "number": "90-01"})[:2]
            assert fr["work_id"] == ar["work_id"] and ar["twin_rule"] == "R-TWIN-CONFIRME" and ar["date_before_pairing"] == "1990-06-04"
        finally:
            relations.OVERRIDES_FILE = old


def test_dead_links_are_deduplicated_and_resolved_only_from_official_urls_already_in_the_corpus():
    from boa_pipeline.deadlinks import attach_to_documents, reconcile
    old = "https://www.bank-of-algeria.dz/pdf/instructions2017/instruction022017.pdf"
    new = "https://www.bank-of-algeria.dz/stoodroa/2021/02/instruction022017.pdf"
    doc = {"document_id": "INS-02-17.fr", "work_id": "INS-02-17", "type_code": "INS", "number": "02-2017", "date": "2017-03-01", "title": "Instruction n°02-2017 relative aux opérations d'escompte",
           "document_url": new, "alias_urls": [], "media_library_alternates": []}
    failed = [{"url": old, "title": "Instruction n°02-2017 du 1 er mars 2017", "stage": "download", "reason": "non téléchargé"}, {"url": old, "title": None, "stage": "download"},
              {"url": "https://www.bank-of-algeria.dz/pdf/reglements1990/inconnu.pdf", "title": "Règlement n°90-99", "stage": "download"}]
    cands = {old: {"type_code": "INS", "number": "02-2017", "date": "2017-03-01", "all_source_pages": ["https://www.bank-of-algeria.dz/annee-2017/"]}}
    out = reconcile(failed, [doc], cands)
    assert len(out) == 2                                                                # 3 entrées, 2 URLs uniques (la phase 3 comptait chaque lien deux fois)
    moved = next(x for x in out if x["url"] == old)
    assert moved["resolution"] == "MOVED_OFFICIAL" and moved["resolved_documents"][0]["official_url"] == new and moved["confidence"].startswith("forte")
    broken = next(x for x in out if x["resolution"] == "BROKEN_SOURCE")
    assert broken["resolved_documents"] == [] and "absent" in broken["note"]            # aucune URL devinée : l'information est conservée
    attach_to_documents(out, [doc])
    assert doc["dead_source_urls"][0]["url"] == old and doc["document_url"] == new       # l'ancienne URL est conservée comme alias mort, jamais comme URL de référence
    # même nom de fichier mais autre numéro de texte : pas de confiance forte
    other = dict(doc, document_id="INS-09-99.fr", work_id="INS-09-99", number="09-99")
    weak = reconcile(failed[:1], [other], cands)[0]
    assert weak["resolution"] == "MOVED_OFFICIAL" and weak["confidence"].startswith("moyenne")


def test_incoming_relation_points_to_the_french_document_not_to_its_arabic_twin():
    """Phase 3 : 31 relations d'un texte FR (« modifié par … ») désignaient le jumeau ARABE du texte modificateur ; le texte modificateur n'était donc pas remonté (G038 : REG-24-05 / REG-16-02)."""
    base = {"type_code": "REG", "date": "2024-10-13", "document_url": "u", "_units": [], "title_document": None}
    mod_fr = dict(base, number="24-05", language="fr", title="Règlement n°24-05 du 13 octobre 2024 modifiant et complétant le règlement n°16-02 du 21 avril 2016 fixant le seuil", url_hash="a1" * 8)
    mod_ar = dict(base, number="24-05", language="ar", title="نظام رقم 24-05 المؤرخ في 13 أكتوبر 2024", url_hash="a2" * 8)
    tgt_fr = dict(base, number="16-02", date="2016-04-21", language="fr", title="Règlement n°16-02 du 21 avril 2016 fixant le seuil", url_hash="b1" * 8)
    for order in ([mod_ar, mod_fr, tgt_fr], [tgt_fr, mod_fr, mod_ar]):                 # l'ordre des documents ne doit pas changer le résultat
        docs = [dict(d) for d in order]
        assign_ids(docs)
        relations.link_documents(docs)
        tgt = next(d for d in docs if d["number"] == "16-02")
        assert [e["document_id"] for e in tgt["modifie_par"]] == ["REG-24-05.fr"] * len(tgt["modifie_par"]) and tgt["modifie_par"]


def _corpus_dirs():
    import os
    out = []
    if os.environ.get("AGENT_CORPUS_DIR"):
        out.append(Path(os.environ["AGENT_CORPUS_DIR"]))
    out.append(ROOT / "corpus" / "chunks")
    return [d for d in out if d.exists()]


def test_chunk_ids_are_unique_in_the_built_corpus():
    """Garde-fou sur le corpus construit (vivant, ou instantané donné par AGENT_CORPUS_DIR) : aucun identifiant de chunk dupliqué, toutes langues confondues."""
    checked = 0
    for d in _corpus_dirs():
        files = [d / f"chunks_{lg}.jsonl" for lg in ("fr", "ar", "und") if (d / f"chunks_{lg}.jsonl").exists()]
        if not files:
            continue
        ids = [json.loads(l)["chunk_id"] for f in files for l in open(f, encoding="utf-8") if l.strip()]
        dup = sorted({i for i in ids if ids.count(i) > 1}) if len(ids) != len(set(ids)) else []
        assert not dup, f"{d} : {len(dup)} chunk_id dupliqués, ex. {dup[:3]}"
        checked += 1
    print("   corpus vérifiés :", checked)


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
