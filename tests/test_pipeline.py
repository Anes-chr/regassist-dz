"""Tests unitaires légers (sans réseau) : python -m pytest tests  ou  python tests/test_pipeline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boa_pipeline.classify import classify_link, parse_date, parse_number, detect_type
from boa_pipeline.clean import clean_pages, reflow
from boa_pipeline.relations import find_relations, num_key
from boa_pipeline.structure import parse_structure


def pages(*texts):
    return [{"page": i + 1, "text": t, "method": "pdf_text"} for i, t in enumerate(texts)]


def test_classification_fr():
    c = classify_link("https://x/y.pdf", "Règlement n°25-07 du 28 Moharram 1447 correspondant au 24 septembre 2025 relatif à X", "https://x/p/", "")
    assert c["type_code"] == "REG" and c["number"] == "25-07" and c["date"] == "2025-09-24"


def test_classification_ar():
    assert detect_type("نظام رقم 06-01 المؤرخ في 14 مايو 2006") == "REG"
    assert parse_number("قانون رقم 17 مؤرخ في 20 محرم عام 1439 الموافق 11 اكتوبر سنة 2017 ، يتمم الأمر رقم 03-11") is None
    assert parse_date("أمر رقم 03-11 مؤرخ 27 جمادى الثانية عام 1424 الموافق 26 غشت سنة 2003")[0] == "2003-08-26"


def test_structure_articles_and_context():
    txt = "REGLEMENT N°1-01\nVu la loi ;\nCHAPITRE I\nDISPOSITIONS GENERALES\nArticle 1er : Objet du texte.\nsuite de la phrase\nArticle 2 : Autre.\nCHAPITRE II\nArticle 3 : Fin."
    st = parse_structure(clean_pages(pages(txt))[0], "fr")
    arts = [u for u in st["units"] if u["kind"] == "article"]
    assert [a["number"] for a in arts] == ["1", "2", "3"]
    assert arts[2]["context"]["chapitre"]["number"] == "II"
    assert arts[0]["text"].startswith("Objet du texte. suite de la phrase".split(".")[0])


def test_reference_inside_text_is_not_article_header():
    txt = "Article 1 : Texte.\nArticle 5 du règlement n°91-09 est modifié.\nArticle 2 : Suite."
    st = parse_structure(clean_pages(pages(txt))[0], "fr")
    assert [u["number"] for u in st["units"] if u["kind"] == "article"] == ["1", "2"]


def test_repeated_header_and_page_number_removed_but_text_kept():
    ps = pages(*[f"BANQUE D'ALGERIE - RAPPORT\nArticle {i} : contenu {i}\n{i}" for i in range(1, 5)])
    out, log = clean_pages(ps)
    assert all("BANQUE D'ALGERIE" not in "\n".join(p["lines"]) for p in out)
    assert any("contenu 3" in "\n".join(p["lines"]) for p in out)
    assert len(log) >= 4


def test_relations_title_only_strong_and_no_false_text_relation():
    r = find_relations("Instruction n°02-2017 du 1er mars 2017 complétant l'instruction n°02-2016 du 24 mars 2016", "title")
    assert [(x["relation"], x["target_ref"]["number"]) for x in r] == [("complete", "02-2016")]
    # « le règlement A complétant le règlement B » dans un article ne concerne pas CE document
    assert find_relations("En application du règlement n°16-03 du 28 juillet 2016 complétant le règlement n°15-01 du 19 février 2015", "text") == []
    r = find_relations("La présente instruction abroge l'instruction n°05-2016 du 01 septembre 2016.", "text")
    assert r and r[0]["relation"] == "abroge"


def test_num_key_tolerates_year_format():
    assert num_key("2014-03") == num_key("14-03")


def test_own_date_is_the_one_after_the_documents_own_number_not_a_cited_texts_date():
    """Mesuré : 43 documents français avaient la date d'un texte CITÉ dans leur intitulé (ex. 1991 au lieu de 2003)."""
    from boa_pipeline.classify import parse_date
    assert parse_date("Règlement n°2002-04 du 9 janvier 2003 complétant le règlement n°91-08 du 14 août 1991 portant organisation")[0] == "2003-01-09"
    assert parse_date("Instruction n°09-2016 du 26 octobre modifiant l’instruction n°02-09 du 25 février 2009")[0] == "2016-10-26"         # année absente : déduite du numéro
    assert parse_date("REGLEMENT N°2016-03 AU 28 JUILLET 2016 COMPLETANT LE REGLEMENT N°15-01 DU 19 FEVRIER 2015")[0] == "2016-07-28"
    assert parse_date("INSTRUCTION N°05-2007 11 JUIN 2007 MODIFIANT ET COMPLETANT L'INSTRUCTUION N°02-2007 DU 31 MAI 2007")[0] == "2007-06-11"
    assert parse_date("Règlement n° 24-02 DU 25 RADJAB 1445 correspondant au 06 février 2024 relatif au capital minimum")[0] == "2024-02-06"   # hégirien -> « correspondant au »
    # texte sans date propre qui cite la date d'un autre texte : AUCUNE date plutôt qu'une date fausse
    assert parse_date("Note aux banques n°01 – 2023 relative aux seuils. Conformément à l’instruction n°08-16 du 1er septembre 2016, relative aux modalités")[0] is None


def test_garbled_text_layer_is_detected_and_clean_text_is_not():
    """76 PDF arabes « natifs » avaient une couche texte illisible (lettres remplacées par des caractères de contrôle) : l'OCR doit prendre le relais pour ces pages."""
    from boa_pipeline.extract import text_layer_garbled
    garbled = "E ,`_\nا\x15[)3ات ا\x15\x07\x0bا\x17\x06 \x15/ 0\x07/ \x1dت ا\x15\x07eآ'رة \x17\x16 ا\x15\x07\x1dدة 15 vq$ أ '\x81'ع " * 3
    clean_ar = "يهدف هذا النظام إلى تحديد القواعد والشروط والإجراءات التي يطبقها بنك الجزائر فيما يخص عمليات خصم السندات العمومية. " * 2
    assert text_layer_garbled(garbled, "ar") and text_layer_garbled("abc\x03\x15\x07 " * 40, "fr")
    assert not text_layer_garbled(clean_ar, "ar") and not text_layer_garbled("Texte français normal, sans défaut. " * 10, "fr")
    assert not text_layer_garbled("court", "ar")                      # trop court pour conclure


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
