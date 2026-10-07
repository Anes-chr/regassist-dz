"""Tests du statut juridique (agent_fr/legal_status.py) sur un mini-corpus synthétique : chaque règle documentée est exercée,
et la règle de principe est vérifiée : une valeur plus récente n'abroge JAMAIS une valeur plus ancienne sans preuve."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_fr import legal_status as L  # noqa: E402


def doc(w, title, number, date, typ="instruction", **rel):
    d = {"document_id": f"{w}.fr", "work_id": w, "title": title, "document_type": typ, "number": number, "date": date, "language": "fr"}
    d.update(rel)
    return d


def chunk(w, art, text, date, kind="article"):
    return {"chunk_id": f"{w}.fr::article-{art}", "document_id": f"{w}.fr", "work_id": w, "unit_kind": kind, "article": art, "text": text, "date": date,
            "language": "fr", "page_number": 1}


def rel(w, date, source="text", partial=False, quote="q"):
    return {"work_id": w, "document_id": f"{w}.fr", "date": date, "partial": partial, "evidence": {"source": source, "page": 1, "quote": quote}}


def test_abrogation_in_title_is_high_confidence_and_text_is_medium():
    docs = [doc("A", "Instruction n°01-2000 fixant X", "01-2000", "2000-01-01", abroge_par=[rel("B", "2001-01-01", "title")]),
            doc("B", "Instruction n°01-2001 abrogeant l'instruction n°01-2000", "01-2001", "2001-01-01", abroge=[rel("A", None, "title")]),
            doc("C", "Instruction n°02-2000 fixant Y", "02-2000", "2000-02-01", abroge_par=[rel("D", "2002-01-01", "text")]),
            doc("D", "Instruction n°01-2002 fixant Y", "01-2002", "2002-01-01", abroge=[rel("C", None, "text")])]
    r = L.build(docs, [])["documents"]
    assert (r["A"]["statut"], r["A"]["confiance"], r["A"]["regle"]) == ("ABROGATED", "HIGH", "R-ABR-TITRE")
    assert (r["C"]["statut"], r["C"]["confiance"], r["C"]["regle"]) == ("ABROGATED", "MEDIUM", "R-ABR-TEXTE")
    assert r["B"]["statut"] == "ACTIVE" and r["B"]["regle"] == "A-DERNIER"


def test_newer_value_never_abrogates_without_evidence():
    """Deux textes sur le même sujet, le second plus récent, aucune relation : AUCUN n'est abrogé ; les deux sont UNKNOWN."""
    docs = [doc("A", "Instruction n°01-2000 fixant le plafond", "01-2000", "2000-01-01"), doc("B", "Instruction n°01-2005 fixant le plafond", "01-2005", "2005-01-01")]
    r = L.build(docs, [])["documents"]
    assert r["A"]["statut"] == "UNKNOWN" and r["B"]["statut"] == "UNKNOWN" and r["A"]["regle"] == "U-ISOLE"


def test_partial_abrogation_is_modified_not_abrogated():
    docs = [doc("A", "Instruction n°01-2000 fixant X", "01-2000", "2000-01-01", abroge_par=[rel("B", "2001-01-01", "text", partial=True)]),
            doc("B", "Instruction n°01-2001 fixant Z", "01-2001", "2001-01-01", abroge=[rel("A", None, "text", partial=True)])]
    r = L.build(docs, [])["documents"]
    assert r["A"]["statut"] == "MODIFIED"


def test_incoherent_relation_date_gives_unknown():
    docs = [doc("A", "Instruction n°01-2005 fixant X", "01-2005", "2005-01-01", abroge_par=[rel("B", "2001-01-01", "text")]),
            doc("B", "Instruction n°01-2001 fixant X", "01-2001", "2001-01-01", abroge=[rel("A", None, "text")])]
    r = L.build(docs, [])["documents"]
    assert r["A"]["statut"] == "UNKNOWN" and r["A"]["regle"] == "U-INCOHERENT"


def test_article_chain_A_B_C_only_last_version_is_active():
    docs = [doc("A", "Instruction n°01-2000 relative au taux", "01-2000", "2000-01-01"),
            doc("B", "Instruction n°01-2005 modifiant l'instruction n°01-2000", "01-2005", "2005-01-01", modifie=[rel("A", None, "title")]),
            doc("C", "Instruction n°01-2010 modifiant l'instruction n°01-2000", "01-2010", "2010-01-01", modifie=[rel("A", None, "title")])]
    docs[0]["modifie_par"] = [rel("B", "2005-01-01", "title"), rel("C", "2010-01-01", "title")]
    chunks = [chunk("A", "3", "Le taux est fixé à 5 %.", "2000-01-01"),
              chunk("B", "2", "L'article 3 de l'instruction n° 01-2000 du 1 janvier 2000 est modifié et rédigé comme suit : « Le taux est fixé à 4 % ».", "2005-01-01"),
              chunk("C", "2", "L'article 3 de l'instruction n° 01-2000 du 1 janvier 2000 est modifié et rédigé comme suit : « Le taux est fixé à 3 % ».", "2010-01-01")]
    out = L.build(docs, chunks)
    a = out["articles"]
    assert a["A::3"]["statut"] == "REPLACED" and a["B::2"]["statut"] == "REPLACED" and a["C::2"]["statut"] == "ACTIVE"
    assert a["C::2"]["regle"] == "A-ART-COURANT" and a["B::2"]["version_de"] == "A::3"
    assert out["documents"]["A"]["statut"] == "MODIFIED"


def test_complement_is_modified_not_replaced():
    docs = [doc("A", "Instruction n°01-2000 relative au taux", "01-2000", "2000-01-01"), doc("B", "Instruction n°01-2005 relative au taux", "01-2005", "2005-01-01")]
    chunks = [chunk("A", "3", "Le taux est fixé à 5 %.", "2000-01-01"),
              chunk("B", "2", "L'article 3 de l'instruction n° 01-2000 est complété comme suit : « Il peut être majoré ».", "2005-01-01")]
    a = L.build(docs, chunks)["articles"]
    assert a["A::3"]["statut"] == "MODIFIED" and a["A::3"]["regle"] == "R-ART-COMPL"


def test_periodic_series_older_periods_are_historical_not_abrogated():
    t = "Instruction n°0{n}-200{y} portant détermination du taux de la prime due au titre de la participation au fonds de garantie"
    docs = [doc(f"S{y}", t.format(n=y, y=y), f"0{y}-200{y}", f"200{y}-06-01") for y in (1, 2, 3, 4)]
    chunks = [chunk(f"S{y}", "2", f"Le taux de la prime est fixé pour l'exercice 200{y - 1} à 0,25 %.", f"200{y}-06-01") for y in (1, 2, 3, 4)]
    out = L.build(docs, chunks)
    d = out["documents"]
    assert [d[f"S{y}"]["statut"] for y in (1, 2, 3)] == ["HISTORICAL"] * 3 and d["S3"]["regle"] == "S-ECHUE" and d["S3"]["confiance"] == "HIGH"
    assert d["S4"]["statut"] == "ACTIVE" and d["S4"]["regle"] == "S-DERNIERE"
    assert not any(v["statut"] == "ABROGATED" for v in d.values())
    assert d["S2"]["periode"]["debut"] == 2001 and len(out["series"]) == 1          # période = exercice (ici l'année PRÉCÉDENTE de la signature)


def test_series_requires_explicit_period_evidence():
    t = "Instruction n°0{n}-200{y} portant détermination du taux de la prime due"
    docs = [doc(f"S{y}", t.format(n=y, y=y), f"0{y}-200{y}", f"200{y}-06-01") for y in (1, 2, 3)]
    chunks = [chunk(f"S{y}", "2", "Le taux de la prime est fixé à 0,25 %.", f"200{y}-06-01") for y in (1, 2, 3)]   # aucune période dans le texte
    out = L.build(docs, chunks)
    assert not out["series"] and all(v["statut"] == "UNKNOWN" for v in out["documents"].values())


def test_visa_reference_to_a_modified_text_is_not_an_amendment():
    """« l'article 118 de l'ordonnance n° 03-11 du 26 août 2003, modifiée et complétée » (renvoi) n'est PAS un amendement de l'article 118."""
    txt = ("Le plafond s'applique conformément à la notion de dépôt unique consacrée par l'article 118 de l'ordonnance n°03-11 du 26 août 2003, modifiée et complétée, susvisée.")
    assert L.amendments(txt) == []
    real = "L'article 3 de l'instruction n° 02-2004 du 13 mai 2004 relative au régime est modifié et rédigé comme suit : « ... »."
    a = L.amendments(real)
    assert len(a) == 1 and a[0]["verbe"] == "modifie" and a[0]["article"] == "3"
    typo = "L'article 11 de l'instruction n°74-94 du 29 novembre 1994 citée ci-dessus et complété comme suit : « ... »."
    assert [x["verbe"] for x in L.amendments(typo)] == ["complete"]


def test_unknown_status_when_legal_file_missing(tmp_path=None):
    legal = L.Legal(None)
    st = legal.status_for_chunk({"work_id": "X", "article": "1"})
    assert st["statut"] == "UNKNOWN" and not legal.available


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
