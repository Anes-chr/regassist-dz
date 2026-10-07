"""Phase 4 — valeurs réglementaires critiques et OCR_UNCERTAIN : « 2,75 % », « 902.75 », « 1 % », « 2 000 000 DA », « 600 000 DA », « 1997 », « 2025 », « Article 25 », « Règlement 25-07 ».
Une valeur OCR suspecte n'est JAMAIS normalisée en silence : elle est signalée (OCR_UNCERTAIN), le texte reste celui de l'OCR. Lancer : python tests/test_ocr_numeric.py (sans réseau)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boa_pipeline.chunk import make_chunks
from boa_pipeline.ocr_check import annotate_document, internal_anomalies, unit_anomalies
from boa_pipeline.ocr_entities import amounts, article_numbers, dates, numbers, percentages, text_numbers
from agent_fr.answer import ocr_warnings

FR_RATE = "Le taux d'intérêt directeur applicable aux opérations principales de refinancement est fixé à 2,75 %."


def test_critical_values_are_read_in_both_languages_without_rewriting_the_text():
    assert percentages("fixé à 2,75 %") == ["2.75"] and percentages("%2.75 ب") == ["2.75"] and percentages("٢,٧٥ %") == ["2.75"]
    assert "2000000" in numbers("limité à 2 000 000 DA par déposant") and amounts("limité à 2 000 000 DA par déposant") == ["2000000"]
    assert amounts("ستمائة ألف (600.000) دينار جزائري") == ["600000"] and "600000" in numbers("بمبلغ 600 000 DA")
    assert amounts("يحدد الحد الأقصى للتعويض بمليوني دينار جزائري2 000 000دج") == ["2000000"]
    assert "1997" in numbers("المؤرخ في 1997") and "2025" in numbers("Instruction du 17 juillet 2025")
    assert article_numbers("Article 25 : Les banques\nArticle 26 : …", "fr") == ["25", "26"] and article_numbers("المادة 25 :\nالمادة 26", "ar") == ["25", "26"]
    assert text_numbers("Règlement n° 25-07 du", "fr") == text_numbers("النظام رقم 07-25 المؤرخ", "ar") == [("07", "25")]     # l'arabe écrit parfois année-numéro, parfois numéro-année
    assert dates("du 23 décembre 2008", "fr") == dates("23 ديسمبر2008", "ar") == [(2008, 12, 23)]


def test_902_75_for_2_75_is_flagged_not_normalised():
    ar = "يحدد معدل الفائدة التوجيهي المطبق على عمليات إعادة التمويل الرئيسية ب 902.75"
    an = unit_anomalies(ar, FR_RATE)
    toks = {(a["token"], a["reason"]) for a in an}
    assert ("902.75", "R-OCR-ABSENT-JUMEAU") in toks and ("2.75", "R-OCR-MANQUANT") in toks
    assert [a for a in an if a["token"] == "902.75"][0]["expected_in_french"] == ["2.75"]            # la valeur du jumeau est donnée pour COMPARAISON, jamais substituée
    assert "902.75" in ar                                                                              # le texte arabe n'est pas modifié
    glyph = [a for a in an if a["token"] == "902.75"][0]
    assert glyph["severity"] == "critique" and glyph["value_in_french_text"] == "2.75" and "R-OCR-PCT-GLYPH" in glyph["likely_cause"]   # cause la plus fréquente : « % » lu « 90 » / « 00 »
    assert [a["severity"] for a in unit_anomalies("المؤرخ في 23 ديسمبر 2005", "du 23 décembre 2008")] == ["info"]                     # entier non corroboré : information, pas d'alerte


def test_correct_ocr_value_is_not_flagged():
    assert unit_anomalies("يحدد معدل الفائدة التوجيهي ب %2.75", FR_RATE) == []
    assert unit_anomalies("يحدد معدل الاحتياطيات الإجبارية ب 1 % من الوعاء", "Le taux des réserves obligatoires est fixé à 1 % de l'assiette.") == []


def test_rate_above_100_percent_and_garbled_percent_symbol_are_flagged_without_french_twin():
    assert any(a["reason"] == "R-OCR-TAUX" for a in internal_anomalies("بمعدل 902.75 %"))
    assert any(a["reason"] == "R-OCR-SYMBOLE" for a in internal_anomalies("ب 2,50 ١ %o"))
    assert any(a["reason"] == "R-OCR-SYMBOLE" for a in internal_anomalies("يحدد المعدل ب 2,50 ١ %"))


def test_misread_year_and_amount_are_flagged_but_hijri_years_and_numbers_in_words_are_not():
    assert any(a["token"] == "2005" for a in unit_anomalies("المؤرخ في 23 ديسمبر 2005", "du 23 décembre 2008"))
    assert any(a["token"] == "10000000" for a in unit_anomalies("مبلغ 10 000 000 دج", "un montant de 10 000 000 000 DA"))
    assert unit_anomalies("المؤرخ في 15 شوال عام 1446", "du 15 chaoual 1446 correspondant au 14 avril") == []              # année hégirienne : jamais signalée
    assert unit_anomalies("يحدد بخمسين بالمائة من الأموال الخاصة", "fixé à 50 % des fonds propres") == []                     # nombre en lettres, aucun chiffre arabe : rien à comparer


def test_value_displaced_by_article_misnumbering_is_not_flagged_when_it_exists_elsewhere_in_the_french_text():
    ar = "المادة 3 : معدل 2.75 %"
    assert unit_anomalies(ar, "Article 3 : taux de 1 %.", fr_doc_nums={"2.75", "1"}, ar_doc_nums={"2.75", "1"}) == []


def _unit(kind, number, text):
    return {"kind": kind, "number": number, "label": f"Article {number}", "heading": None, "context": {}, "annexe": None, "paragraphs": [{"text": text, "page_start": 1, "page_end": 1}], "text": text}


def test_annotation_reaches_the_chunk_and_the_warning_quotes_the_doubtful_value():
    ar = {"_units": [_unit("article", "2", "يحدد المعدل ب 902.75"), _unit("article", "3", "تدخل هذه التعليمة حيز التطبيق")]}
    fr = {"_units": [_unit("article", "2", FR_RATE), _unit("article", "3", "La présente instruction prend effet.")]}
    summary = annotate_document(ar, fr)
    assert summary["units_flagged"] == 1 and summary["units_compared_with_french"] == 2
    doc = {"document_id": "INS-08-25.ar", "work_id": "INS-08-25", "title": "t", "document_type": "instruction", "number": "08-2025", "date": "2025-08-31", "publication_date": None,
           "language": "ar", "status": "x", "source_url": "u", "document_url": "u", "extraction_method": "ocr", "needs_manual_review": False}
    chunks = make_chunks(doc, ar["_units"])
    flagged = [c for c in chunks if c.get("ocr_uncertain")]
    assert len(flagged) == 1 and "902.75" in flagged[0]["text"] and flagged[0]["ocr_uncertain_tokens"][0]["reason"].startswith("R-OCR")
    shown = [{"id": "S1", "ocr_uncertain_tokens": flagged[0]["ocr_uncertain_tokens"]}]
    w = ocr_warnings(shown, "Le taux est de 902.75 % [S1].")
    assert len(w) == 1 and "OCR_UNCERTAIN" in w[0] and "902.75" in w[0] and w[0].startswith("⚠ La réponse reprend la valeur douteuse 902.75")
    assert ocr_warnings(shown, "Le taux n'est pas précisé.")[0].startswith("[S1] OCR_UNCERTAIN")
    assert ocr_warnings([{"id": "S2", "ocr_uncertain_tokens": []}], "x") == []


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
