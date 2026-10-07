"""Construit le BROUILLON du benchmark juridique indépendant (phase 3) : benchmark_v1_draft.jsonl.

Statut : questions et réponses attendues RÉDIGÉES PAR UNE IA (Claude) à partir des textes officiels du corpus, chaque passage cité étant vérifié mécaniquement (citation textuelle
retrouvée dans le chunk). Elles ne sont PAS validées juridiquement : `validation_humaine.statut = "en_attente"` tant qu'un juriste n'a pas relu (paquet : packs.py review).

Méthode de rédaction (fixée avant toute mesure) :
  - plusieurs questions par « thème » (une chaîne de textes, une série, un article) ; TOUTES les questions d'un thème vont dans le MÊME split (pas de fuite DEV → TEST) ;
  - la répartition DEV / TEST se fait par thème, par tirage à graine fixe (SEED) dans chaque type, sans regarder le comportement du système ;
  - TEST : on ne l'exécute qu'une fois, après validation humaine et gel des règles de recherche.
Chaque item : champs du cahier des charges + `sources_attendues` et `versions_acceptables / versions_interdites` pour la notation (voir bench.py).
"""
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent_fr.eval.human.bench import Corpus, verify_item  # noqa: E402

HERE = Path(__file__).resolve().parent
SEED = 20261006
CORPUS = Corpus(os.environ.get("AGENT_CORPUS_DIR"))
ITEMS = []          # (theme, item)


def passage(work, art, quote, alternatives=None):
    p = {"work_id": work, "article": art, "citation": quote}
    if alternatives:
        p["alternatives"] = alternatives
    return p


def add(theme, type_, q, passages, answer, facts=None, *, domaine, date_ref=None, statut=None, difficulte="moyen", langue="fr", sous_type=None,
        acceptables=None, interdites=None, comportement="repondre", temporalite=False, applicable_a_la_date=None, note=None, mode=None, chaine=None):
    it = {
        "id": None, "split": None, "type_de_question": type_, "sous_type": sous_type, "question": q, "langue": langue, "domaine": domaine,
        "document_attendu": [{"work_id": w, "titre": (CORPUS.docs.get(w) or {}).get("title"), "url_officielle": (CORPUS.docs.get(w) or {}).get("document_url")}
                             for w in dict.fromkeys(p["work_id"] for p in passages)],
        "article_attendu": [{"work_id": p["work_id"], "article": p["article"]} for p in passages] or None,
        "passage_attendu": passages, "reponse_attendue": answer, "faits_cles": facts or [], "date_de_reference": date_ref, "statut_juridique": statut,
        "applicable_a_la_date_de_reference": applicable_a_la_date, "niveau_de_difficulte": difficulte, "attendu_comportement": comportement,
        "redaction": {"auteur": "IA (Claude)", "date": "2026-10-06", "theme": theme},
        "validation_humaine": {"statut": "en_attente", "validateur": None, "date": None, "commentaire": None},
    }
    if type_ == "E_abrogation" and passages and passages[0].get("alternatives"):
        it["sujet"] = dict(passages[0]["alternatives"][0])        # le statut attendu porte sur le TEXTE INTERROGÉ, pas sur le passage qui en apporte la preuve
    if acceptables:
        it["versions_acceptables"] = acceptables
    if interdites:
        it["versions_interdites"] = interdites
    if temporalite:
        it["sous_benchmark"] = ["temporalite"]
    if mode:
        it["mode"] = mode
    if chaine:
        it["chaine_id"] = chaine
    if note:
        it["note_redacteur"] = note
    ITEMS.append((theme, it))
    return it


def refuse(theme, type_, q, domaine, answer="Je ne trouve pas de disposition correspondante dans le corpus disponible.", difficulte="facile", langue="fr", absent=None):
    if absent:                                   # hors corpus : on VÉRIFIE que le sujet est absent de tous les passages (FR + AR)
        import re
        hit = [c["chunk_id"] for c in CORPUS.chunks if re.search(absent, c["text"], re.I)]
        assert not hit, f"le corpus contient « {absent} » : {hit[:3]}"
    return add(theme, type_, q, [], answer, domaine=domaine, comportement="refuser", difficulte=difficulte, langue=langue)


def clarify(theme, q, domaine, answer="Le système doit demander de préciser le texte, le sujet ou la période.", langue="fr"):
    return add(theme, "G_ambigue", q, [], answer, domaine=domaine, comportement="clarifier", langue=langue)


def forb(work, art, why):
    return {"work_id": work, "article": art, "raison": why}


def acc(work, art):
    return {"work_id": work, "article": art}


# =====================================================================================================================================================
# THÈME : capital minimum des banques (chaîne 90-01 > 2004-01 > 2008-04 > 2018-03 > 24-02) — texte entier remplacé à chaque étape, abrogation expresse
# =====================================================================================================================================================
T = "capital_minimum"
Q90 = passage("REG-90-01-19900704", "1", "500 millions de dinars algériens pour les banques")
Q04 = passage("REG-04-01", "2", "deux milliards cinq cent millions de dinars (2.500.000.000 DA) pour les banques")
Q08 = passage("REG-08-04-20081223", "2", "Dix milliards de dinars (10 000 000 000 DA) pour les banques")
Q08ef = passage("REG-08-04-20081223", "2", "Trois milliards cinq cent millions de dinars (3 500 000 000 DA) pour les établissements financiers")
Q18 = passage("REG-18-03", "2", "Vingt milliards de dinars (20 000 000 000 DA) pour les banques")
Q24 = passage("REG-24-02", "2", "a. Banque : vingt milliards de dinars algériens (20 000 000 000 DA)")
OLD_CAP = [forb("REG-90-01-19900704", "1", "abrogé par REG-04-01"), forb("REG-04-01", "2", "abrogé par REG-08-04"), forb("REG-08-04-20081223", "2", "abrogé par REG-18-03"),
           forb("REG-18-03", "2", "abrogé par REG-24-02")]

add(T, "C_temporelle", "Quel est le capital minimum exigé d'une banque exerçant en Algérie aujourd'hui ?", [Q24],
    "20 milliards de dinars algériens pour une banque (règlement n° 24-02), à détenir à tout moment ; les autres catégories ont d'autres montants.",
    [["20 000 000 000", "vingt milliards", "20 milliards"]], domaine="prudentiel", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle",
    acceptables=[acc("REG-24-02", "2")], interdites=OLD_CAP, chaine="cap_min")
add(T, "C_temporelle", "Quel était le capital minimum d'une banque en 2005 ?", [Q04],
    "2,5 milliards de dinars (règlement n° 2004-01, applicable de 2004 à son abrogation en 2008).", [["2.500.000.000", "2 500 000 000", "deux milliards cinq cent millions", "2,5 milliards"]],
    domaine="prudentiel", date_ref="2005-06-30", statut="ABROGATED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("REG-04-01", "2")], interdites=[forb("REG-90-01-19900704", "1", "abrogé en 2004"), forb("REG-08-04-20081223", "2", "postérieur"),
                                                       forb("REG-18-03", "2", "postérieur"), forb("REG-24-02", "2", "postérieur")], chaine="cap_min")
add(T, "C_temporelle", "Quel était le capital minimum exigé d'un établissement financier en 2010 ?", [Q08ef],
    "3,5 milliards de dinars (règlement n° 2008-04).", [["3 500 000 000", "3.500.000.000", "trois milliards cinq cent millions", "3,5 milliards"]],
    domaine="prudentiel", date_ref="2010-06-30", statut="ABROGATED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("REG-08-04-20081223", "2")], interdites=[forb("REG-04-01", "2", "abrogé en 2008"), forb("REG-18-03", "2", "postérieur"), forb("REG-24-02", "2", "postérieur")],
    chaine="cap_min")
add(T, "C_temporelle", "Quel était le capital social minimum d'une banque en 1995 ?", [Q90],
    "500 millions de dinars algériens (règlement n° 90-01), sans être inférieur à 33 % des fonds propres.", [["500 millions"]], domaine="prudentiel", date_ref="1995-06-30",
    statut="ABROGATED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne", difficulte="difficile", acceptables=[acc("REG-90-01-19900704", "1")],
    interdites=[forb("REG-04-01", "2", "postérieur"), forb("REG-08-04-20081223", "2", "postérieur"), forb("REG-18-03", "2", "postérieur"), forb("REG-24-02", "2", "postérieur")], chaine="cap_min")
add(T, "E_abrogation", "Le règlement n° 2008-04 relatif au capital minimum des banques et établissements financiers est-il encore applicable ?",
    [passage("REG-18-03", "5", "Les dispositions du Règlement n°08-04 du 23 décembre 2008 relatif au capital minimum des banques et établissements financiers exerçant en Algérie susvisé, sont abrogées",
             alternatives=[acc("REG-08-04-20081223", None)])],
    "Non : il a été abrogé par l'article 5 du règlement n° 2018-03 (lui-même abrogé ensuite par le règlement n° 24-02).", [["18-03", "2018-03"]], domaine="prudentiel",
    date_ref="actuel", statut="ABROGATED", temporalite=True, sous_type="abrogation", chaine="cap_min")
add(T, "E_abrogation", "Le règlement n° 2004-01 sur le capital minimum a-t-il été abrogé, et par quel texte ?",
    [passage("REG-08-04-20081223", "5", "Les dispositions du règlement n°04-01 du 4 mars 2004 relatif au capital minimum des banques et établissements financiers exerçant en Algérie susvisé, sont abrogées",
             alternatives=[acc("REG-04-01", None)])],
    "Oui, par le règlement n° 2008-04 du 23 décembre 2008 (article 5).", [["08-04", "2008-04"]], domaine="prudentiel", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="abrogation", chaine="cap_min")
add(T, "D_modification", "Quel texte a remplacé le règlement n° 2018-03 relatif au capital minimum des banques et établissements financiers ?",
    [passage("REG-24-02", "4", "notamment celles du règlement n°18-03 du 26 Safar 1440 correspondant au 4 novembre 2018", alternatives=[acc("REG-18-03", None)])],
    "Le règlement n° 24-02 du 6 février 2024 (article 4).", [["24-02"]], domaine="prudentiel", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="texte_remplacant", chaine="cap_min")
ITEMS[-1][1]["sujet"] = {"work_id": "REG-18-03", "article": None}      # statut du texte interrogé (abrogé par l'article 4 du règlement 24-02)
add(T, "F_comparaison", "Quelle différence y a-t-il entre le capital minimum exigé d'une banque par le règlement n° 2008-04 et par le règlement n° 24-02 ?", [Q08, Q24],
    "Le règlement 2008-04 exigeait 10 milliards de dinars pour une banque ; le règlement 24-02 exige 20 milliards (et distingue banque d'affaires, banque digitale 10 milliards, établissement financier).",
    [["10 000 000 000", "dix milliards", "10 milliards"], ["20 000 000 000", "vingt milliards", "20 milliards"]], domaine="prudentiel", date_ref="actuel", statut="ACTIVE",
    temporalite=True, mode="all", sous_type="ancien_vs_actuel", difficulte="difficile", chaine="cap_min")
add(T, "B_multi_textes", "Quels règlements ont successivement fixé le capital minimum des banques depuis 2004 ?", [Q04, Q08, Q18, Q24],
    "Les règlements n° 2004-01, n° 2008-04, n° 2018-03 puis n° 24-02.", [["04-01", "2004-01"], ["08-04", "2008-04"], ["18-03", "2018-03"], ["24-02"]], domaine="prudentiel", date_ref="actuel",
    statut="ACTIVE", temporalite=True, mode="all", difficulte="difficile", chaine="cap_min")
add(T, "C_temporelle", "Avant quelle date les banques en activité devaient-elles se conformer au règlement n° 2018-03 relatif au capital minimum ?",
    [passage("REG-18-03", "4", "au plus tard le 31 décembre 2020")], "Au plus tard le 31 décembre 2020 (avec 15 milliards de dinars pour les banques dès le 31 décembre 2019).",
    [["31 décembre 2020"]], domaine="prudentiel", date_ref="2019-06-30", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="date_echeance",
    acceptables=[acc("REG-18-03", "4")], chaine="cap_min")

# =====================================================================================================================================================
# THÈME : prévention du blanchiment d'argent (05-05 > 12-03 > 24-03)
# =====================================================================================================================================================
T = "lbc_ft"
L24 = passage("REG-24-03", "21", "durant une période de cinq (5) ans, au moins, après la fin de la relation d'affaires")
OLD_LBC = [forb("REG-12-03", "8", "abrogé par REG-24-03"), forb("REG-05-05", "8", "abrogé par REG-12-03")]
add(T, "C_temporelle", "Pendant combien de temps les institutions assujetties doivent-elles conserver les documents relatifs à la vigilance à l'égard de la clientèle ?", [L24],
    "Au moins cinq ans après la fin de la relation d'affaires ou de l'opération occasionnelle (règlement n° 24-03, art. 21).", [["cinq (5) ans", "5 ans", "cinq ans"]],
    domaine="lbc_ft", date_ref="actuel", statut="MODIFIED", temporalite=True, sous_type="valeur_actuelle", acceptables=[acc("REG-24-03", "21")], interdites=OLD_LBC, chaine="lbc")
add(T, "E_abrogation", "Le règlement n° 2012-03 relatif à la prévention et à la lutte contre le blanchiment d'argent est-il encore applicable ?",
    [passage("REG-24-03", "51", "notamment le règlement n° 12-03 du 14 Moharram 1434", alternatives=[acc("REG-12-03", None)])],
    "Non : il est abrogé par l'article 51 du règlement n° 24-03 du 24 juillet 2024.", [["24-03"]], domaine="lbc_ft", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="abrogation", chaine="lbc")
add(T, "D_modification", "Quel règlement a abrogé et remplacé le règlement n° 2005-05 relatif à la prévention et à la lutte contre le blanchiment d'argent ?",
    [passage("REG-12-03", "28", "Le présent règlement abroge et remplace le règlement n°2005-05", alternatives=[acc("REG-05-05", None)])],
    "Le règlement n° 2012-03 du 28 novembre 2012 (article 28).", [["12-03", "2012-03"]], domaine="lbc_ft", date_ref="actuel", statut="REPLACED", temporalite=True,
    sous_type="texte_remplacant", chaine="lbc")
ITEMS[-1][1]["sujet"] = {"work_id": "REG-05-05", "article": None}      # statut du texte interrogé
add(T, "A_direct", "Que doivent faire les institutions assujetties si elles ne parviennent pas à identifier et vérifier l'identité de leur client ?", [passage("REG-24-03", "19", "doivent s’abstenir d’ouvrir un compte, d’établir des relations d'affaires ou de réaliser des opérations")],
    "S'abstenir d'ouvrir un compte, d'établir la relation d'affaires ou de réaliser l'opération, ou mettre fin à la relation d'affaires.", [["s’abstenir d’ouvrir un compte", "s'abstenir d'ouvrir un compte"]],
    domaine="lbc_ft", sous_type="obligation", statut="ACTIVE", chaine="lbc")


# =====================================================================================================================================================
# QUESTIONS DIRECTES (A) — articles tirés au sort (graine fixe, textes non utilisés dans les anciens jeux, hors chaînes), pris DANS L'ORDRE du tirage ;
# écartés : textes anciens dont la valeur est probablement modifiée (INS-70-92 art. 7, INS-22-94 art. 2, INS-87-61), articles tronqués ou sans fait précis.
# =====================================================================================================================================================
def direct(key, q, work, art, quote, answer, facts, domaine, sous_type, statut="UNKNOWN", difficulte="facile"):
    # le statut juridique d'un texte isolé n'est pas déterminable avec certitude : on ne le devine pas (None = à renseigner par le juriste, exclu du score de statut)
    add("direct_" + key, "A_direct", q, [passage(work, art, quote)], answer, facts, domaine=domaine, sous_type=sous_type, statut=None, difficulte=difficulte,
        note="statut juridique non évalué : à renseigner par le juriste")


direct("ie26", "Quel est le niveau maximal des engagements extérieurs par signature des banques et établissements financiers ?", "INS-03-26", "2",
       "ne doit dépasser cinquante pourcent (50%) de leurs fonds propres", "50 % de leurs fonds propres réglementaires.", [["50%", "50 %", "cinquante pourcent"]], "prudentiel", "seuil", "ACTIVE")
direct("bch", "De combien les cours des bureaux de change peuvent-ils s'écarter des cours de la Banque d'Algérie pour les billets de banque et chèques de voyage ?", "INS-08-96", "10",
       "peuvent s'écarter de un pour cent (1%) maximum par rapport aux cours pratiqués par la Banque d'Algérie", "De 1 % au maximum.", [["1%", "1 %", "un pour cent"]], "change", "seuil", "MODIFIED")
direct("bd30", "Quelle part du capital une banque de droit algérien doit-elle détenir dans une banque digitale ?", "REG-24-04", "5", "Cette banque doit détenir au moins 30% du capital",
       "Au moins 30 % du capital.", [["30%", "30 %"]], "banque_digitale", "seuil", "UNKNOWN")
direct("exp15", "Dans quel délai la domiciliation des exportations de produits frais, périssables ou dangereux peut-elle avoir lieu ?", "INS-07-21", "2", "durant les quinze (15) jours ouvrés qui suivent la date d’expédition",
       "Durant les quinze jours ouvrés qui suivent la date d'expédition et de déclaration en douanes.", [["quinze (15) jours ouvrés", "15 jours ouvrés", "quinze jours ouvrés"]], "change", "delai")
direct("agr2m", "Dans quel délai la décision d'agrément est-elle notifiée au promoteur d'une société de capital-risque ?", "REG-96-06", "9", "au plus tard deux (2) mois après la remise de tous les éléments",
       "Au plus tard deux mois après la remise de tous les éléments et informations du dossier.", [["deux (2) mois", "2 mois", "deux mois"]], "agrement", "delai", "UNKNOWN", "moyen")
direct("psp3m", "Dans quel délai un prestataire de services de paiement doit-il restituer les fonds aux titulaires de comptes de paiement en cas de retrait d'agrément ?", "INS-06-25", "30",
       "dans un délai n’excédant pas trois (3) mois", "Sans frais, dans un délai n'excédant pas trois mois.", [["trois (3) mois", "3 mois", "trois mois"]], "paiements", "delai")
direct("eff6", "Quelle échéance restant à courir ne doivent pas dépasser les effets privés réescomptables ?", "REG-15-01", "9", "leur échéance restant à courir n’excédant pas six (06) mois",
       "Six mois au plus.", [["six (06) mois", "six (6) mois", "6 mois", "six mois"]], "refinancement", "delai", "MODIFIED", "moyen")
direct("dct", "Quand les déclarations de la dette à court terme doivent-elles parvenir à la Direction de la Dette Extérieure ?", "INS-03-04", "5", "au plus tard à la fin du mois suivant le mois de l’utilisation ou du remboursement",
       "Au plus tard à la fin du mois suivant le mois de l'utilisation ou du remboursement.", [["fin du mois suivant"]], "dette_exterieure", "delai", "UNKNOWN", "moyen")
direct("rapp", "À quelle fréquence le prestataire de services de paiement doit-il rapprocher le compte de cantonnement et les comptes de paiement ?", "INS-06-25", "15",
       "est tenu de rapprocher quotidiennement le solde du ou des comptes de cantonnement", "Quotidiennement.", [["quotidiennement"]], "paiements", "obligation")
direct("cheq", "Que doivent faire les banques à l'égard d'un client qui figure sur la liste des interdits de chéquiers ?", "REG-08-01", "12", "s'abstenir de délivrer un chéquier à tout client qui figure sur cette liste",
       "S'abstenir de lui délivrer un chéquier.", [["s'abstenir de délivrer un chéquier", "s’abstenir de délivrer un chéquier"]], "moyens_de_paiement", "obligation", "MODIFIED")
direct("fict", "Quelle obligation les institutions assujetties ont-elles à l'égard des banques fictives ?", "INS-03-24", "25", "sont tenues de s’abstenir d’établir ou de maintenir toute relation de correspondance bancaire",
       "S'abstenir d'établir ou de maintenir une relation de correspondance bancaire avec des banques fictives.", [["s’abstenir d’établir", "s'abstenir d'établir"]], "lbc_ft", "obligation")
direct("enligne", "Quelle protection les assujettis doivent-ils garantir à la clientèle qui utilise des produits et services en ligne ?", "REG-25-03-20250414", "11", "une protection similaire à celle accordée aux utilisateurs de produits et services bancaires classiques",
       "Une protection similaire à celle des produits et services bancaires classiques.", [["protection similaire"]], "protection_clientele", "obligation")
direct("cdb", "Que doivent porter à la connaissance de leur clientèle les banques et établissements financiers ?", "REG-94-13", "6", "tenus de porter à la connaissance de leur clientèle et du public les conditions de banque qu'ils pratiquent",
       "Les conditions de banque qu'ils pratiquent pour leurs opérations.", [["conditions de banque"]], "conditions_banque", "obligation", "UNKNOWN")
direct("bdnom", "Une entité non agréée comme banque digitale peut-elle utiliser une dénomination ou une publicité faisant croire qu'elle l'est ?", "REG-24-04", "14",
       "Il est interdit à toute entité non agréée en qualité de banque digitale d’utiliser une dénomination", "Non, c'est interdit.", [["interdit"]], "banque_digitale", "interdiction")
direct("aff", "Une banque peut-elle appliquer des conditions moins favorables que celles qu'elle a affichées ?", "INS-77-95", "5", "Aucune banque ou établissement financier ne peut appliquer des conditions moins favorables que celles qu'elle a affichée",
       "Non ; l'emprunteur lésé peut saisir la Commission Bancaire.", [["Aucune banque", "ne peut appliquer des conditions moins favorables"]], "conditions_banque", "interdiction", "ACTIVE")
direct("cdev", "Un compte devises ouvert au nom des personnes visées par le règlement 2009-01 peut-il être débiteur ?", "REG-09-01", "4", "doivent fonctionner exclusivement en situation créditrice et ne peuvent en aucun cas présenter un solde débiteur",
       "Non : il doit fonctionner exclusivement en situation créditrice.", [["situation créditrice"]], "change", "interdiction")
direct("bddef", "Qu'est-ce qu'une banque digitale au sens du règlement n° 24-04 ?", "REG-24-04", "2", "toute banque offrant des services et produits bancaires exclusivement via des canaux, des plates-formes et des supports digitaux",
       "Toute banque offrant des services et produits bancaires exclusivement via des canaux, plates-formes et supports digitaux.", [["exclusivement via des canaux"]], "banque_digitale", "definition")
direct("islam", "Qu'est-ce qu'une opération de banque relevant de la finance islamique selon le règlement n° 20-02 ?", "REG-20-02", "2", "toute opération de banque qui ne donne pas lieu à la perception ou au versement d’intérêts",
       "Toute opération de banque qui ne donne pas lieu à la perception ou au versement d'intérêts (et respecte les dispositions de l'ordonnance).", [["ne donne pas lieu à la perception ou au versement d’intérêts", "ne donne pas lieu à la perception ou au versement d'intérêts"]],
       "finance_islamique", "definition", "ACTIVE")
direct("inv", "Que recouvre l'investissement à l'étranger au sens du règlement n° 14-04 ?", "REG-14-04", "2", "création de société ou de succursale", "La création de société ou de succursale, la prise de participation dans des sociétés existantes et l'ouverture de bureau de représentation.",
       [["création de société ou de succursale"], ["prise de participation"], ["bureau de représentation"]], "investissement_etranger", "definition")
direct("creance", "Que faut-il entendre par créances au sens du règlement n° 14-03 ?", "REG-14-03", "2", "l’ensemble des crédits accordés aux personnes physiques ou morales, inscrits au bilan des banques et établissements financiers",
       "L'ensemble des crédits accordés aux personnes physiques ou morales, inscrits au bilan des banques et établissements financiers.", [["ensemble des crédits accordés"]], "prudentiel", "definition")
direct("ent", "Qui est visé par la notion de banque, établissement financier et succursale au sens du règlement n° 24-01 ?", "REG-24-01", "2", "toute entité créée aux fins d’effectuer à titre de profession habituelle",
       "Toute entité créée aux fins d'effectuer à titre de profession habituelle les opérations de banque et opérations connexes.", [["profession habituelle"]], "general", "definition", "ACTIVE", "moyen")


# =====================================================================================================================================================
# THÈME : taux d'intérêt directeur (INS-07-20 art. 2 > INS-08-25 art. 2 > INS-02-26 art. 2) — chaîne A -> B -> C sur UN article
# =====================================================================================================================================================
T = "taux_directeur"
D20 = passage("INS-07-20", "2", "fixé à 3 % au lieu de 3,25 %")
D25 = passage("INS-08-25", "2", "est fixé à 2,75%")
D26 = passage("INS-02-26", "2", "est fixé à 2,50%")
add(T, "C_temporelle", "Quel est le taux d'intérêt directeur applicable aux opérations principales de refinancement ?", [D26],
    "2,50 % (instruction n° 02-2026 du 7 janvier 2026, qui a remplacé la rédaction de l'article 2 de l'instruction n° 07-2020).", [["2,50%", "2,50 %", "2,5 %", "2,5%"]],
    domaine="politique_monetaire", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle", acceptables=[acc("INS-02-26", "2")],
    interdites=[forb("INS-08-25", "2", "remplacé par INS-02-26"), forb("INS-07-20", "2", "remplacé par INS-08-25 puis INS-02-26")], chaine="taux_dir")
add(T, "C_temporelle", "Quel était le taux d'intérêt directeur de refinancement en 2022 ?", [D20], "3 % (instruction n° 07-2020, en vigueur jusqu'à la modification de 2025).",
    [["3 %", "3%"]], domaine="politique_monetaire", date_ref="2022-06-30", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("INS-07-20", "2")], interdites=[forb("INS-08-25", "2", "postérieur"), forb("INS-02-26", "2", "postérieur")], chaine="taux_dir")
add(T, "C_temporelle", "Quel était le taux d'intérêt directeur de refinancement au 1er novembre 2025 ?", [D25], "2,75 % (instruction n° 08-2025 du 31 août 2025).",
    [["2,75%", "2,75 %"]], domaine="politique_monetaire", date_ref="2025-11-01", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    difficulte="difficile", acceptables=[acc("INS-08-25", "2")], interdites=[forb("INS-07-20", "2", "remplacé en août 2025"), forb("INS-02-26", "2", "postérieur au 1er novembre 2025")],
    chaine="taux_dir")
add(T, "D_modification", "Quelle instruction a ramené le taux d'intérêt directeur à 2,75 % en modifiant l'instruction n° 07-2020 ?", [D25], "L'instruction n° 08-2025 du 31 août 2025 (article 2).",
    [["08-2025", "08-25"]], domaine="politique_monetaire", date_ref="actuel", statut="REPLACED", temporalite=True, sous_type="texte_modificateur", chaine="taux_dir")
add(T, "F_comparaison", "Quelle différence entre le taux d'intérêt directeur fixé par l'instruction n° 07-2020 et celui fixé par l'instruction n° 02-2026 ?", [D20, D26],
    "L'instruction 07-2020 fixait 3 % (au lieu de 3,25 %) ; l'instruction 02-2026 fixe 2,50 %.", [["3 %", "3%"], ["2,50%", "2,50 %", "2,5 %"]], domaine="politique_monetaire", date_ref="actuel",
    statut="ACTIVE", temporalite=True, mode="all", sous_type="ancien_vs_actuel", difficulte="difficile", chaine="taux_dir")
add(T, "E_abrogation", "L'article 2 de l'instruction n° 07-2020 tel que modifié par l'instruction n° 08-2025 est-il encore applicable ?",
    [passage("INS-02-26", "2", "est modifié et rédigé comme suit", alternatives=[acc("INS-08-25", "2")])],
    "Non : l'instruction n° 02-2026 a de nouveau modifié et réécrit l'article 2 de l'instruction n° 07-2020 (taux fixé à 2,50 %).", [["02-2026", "02-26"]], domaine="politique_monetaire",
    date_ref="actuel", statut="REPLACED", temporalite=True, sous_type="article_remplace", difficulte="difficile", chaine="taux_dir")

# =====================================================================================================================================================
# THÈME : réserves obligatoires (INS-02-04 art. 3, 17 réécritures successives)
# =====================================================================================================================================================
T = "reserves"
RES_CHAIN = ["INS-02-04", "INS-13-07", "INS-04-10", "INS-01-12", "INS-02-13", "INS-03-16", "INS-04-17", "INS-01-18",
             "INS-03-18", "INS-01-19", "INS-02-19", "INS-02-20", "INS-06-20", "INS-09-20", "INS-02-21",
             "INS-02-23", "INS-09-25", "INS-01-26"]


def others(keep):
    return [forb(w, "3" if w == "INS-02-04" else "2", "autre version du taux") for w in RES_CHAIN if w != keep]


add(T, "C_temporelle", "Quel est le taux des réserves obligatoires actuellement fixé ?", [passage("INS-01-26", "2", "Le taux des réserves obligatoires est fixé à 1% de l'assiette")],
    "1 % de l'assiette des réserves (instruction n° 01-2026 du 7 janvier 2026, qui réécrit l'article 3 de l'instruction n° 02-2004).", [["1%", "1 %"]], domaine="politique_monetaire", date_ref="actuel",
    statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle", acceptables=[acc("INS-01-26", "2")], interdites=others("INS-01-26"), chaine="reserves")
add(T, "C_temporelle", "Quel était le taux des réserves obligatoires en 2013 ?", [passage("INS-02-13", "2", "Le taux des réserves obligatoires est fixé à 12 % de l'assiette")],
    "12 % de l'assiette des réserves (instruction n° 02-2013 du 23 avril 2013).", [["12 %", "12%"]], domaine="politique_monetaire", date_ref="2013-12-31", statut="REPLACED",
    applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne", acceptables=[acc("INS-02-13", "2")], interdites=others("INS-02-13"), chaine="reserves")
add(T, "C_temporelle", "Quel était le taux des réserves obligatoires au 1er novembre 2020 ?", [passage("INS-09-20", "2", "Le taux des réserves obligatoires est fixé à 3% de l'assiette")],
    "3 % de l'assiette des réserves (instruction n° 09-2020 du 14 septembre 2020).", [["3%", "3 %"]], domaine="politique_monetaire", date_ref="2020-11-01", statut="REPLACED",
    applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne", difficulte="difficile", acceptables=[acc("INS-09-20", "2")], interdites=others("INS-09-20"), chaine="reserves")
add(T, "D_modification", "Quelle instruction a ramené à 1 % le taux des réserves obligatoires ?", [passage("INS-01-26", "2", "Le taux des réserves obligatoires est fixé à 1% de l'assiette")],
    "L'instruction n° 01-2026 du 7 janvier 2026.", [["01-2026", "01-26"]], domaine="politique_monetaire", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur",
    chaine="reserves")
add(T, "E_abrogation", "L'instruction n° 09-2025 qui fixe le taux des réserves obligatoires à 2 % est-elle encore applicable ?",
    [passage("INS-01-26", "2", "Le taux des réserves obligatoires est fixé à 1% de l'assiette", alternatives=[acc("INS-09-25", "2")])],
    "Non : l'instruction n° 01-2026 a réécrit l'article 3 de l'instruction n° 02-2004 et fixe le taux à 1 %.", [["01-2026", "01-26"]], domaine="politique_monetaire", date_ref="actuel",
    statut="REPLACED", temporalite=True, sous_type="article_remplace", chaine="reserves")

# =====================================================================================================================================================
# THÈME : taux de réescompte (chaîne d'instructions, chacune abroge la précédente)
# =====================================================================================================================================================
T = "reescompte"
add(T, "C_temporelle", "Quel est le taux de réescompte actuellement fixé ?", [passage("INS-03-17", None, "le taux de réescompte est fixé à 3,75 %")],
    "3,75 % (instruction n° 03-2017 du 12 avril 2017, en vigueur à compter du 2 mai 2017).", [["3,75"]], domaine="politique_monetaire", date_ref="actuel", statut="ACTIVE", temporalite=True,
    sous_type="valeur_actuelle", acceptables=[acc("INS-03-17", None)], interdites=[forb("INS-05-16", None, "abrogée par INS-03-17"), forb("INS-01-04", None, "abrogée"), forb("INS-01-98", None, "abrogée")],
    chaine="reescompte")
add(T, "C_temporelle", "Quel était le taux de réescompte en juin 1998 ?", [passage("INS-01-98", None, "le taux de réescompte est fixé à 9,5 %")], "9,5 % (instruction n° 01-98 du 8 février 1998).",
    [["9,5"]], domaine="politique_monetaire", date_ref="1998-06-30", statut="ABROGATED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("INS-01-98", None)], interdites=[forb("INS-09-97", None, "abrogée en février 1998"), forb("INS-05-99", None, "postérieure"), forb("INS-03-17", None, "postérieure")], chaine="reescompte")
add(T, "E_abrogation", "L'instruction n° 05-2016 fixant le taux de réescompte est-elle encore applicable ?",
    [passage("INS-03-17", None, "La présente Instruction abroge les dispositions de l’instruction n°05-2016", alternatives=[acc("INS-05-16", None)])],
    "Non : elle est abrogée par l'instruction n° 03-2017 du 12 avril 2017.", [["03-2017", "03-17"]], domaine="politique_monetaire", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="abrogation", chaine="reescompte")

# =====================================================================================================================================================
# THÈME : droit de change pour voyage (INS-08-97 > INS-05-25 > INS-07-26)
# =====================================================================================================================================================
T = "dc_voyage"
add(T, "C_temporelle", "Quel est le montant annuel maximum du droit de change pour voyage à l'étranger ?", [passage("INS-07-26", "2", "sept cent cinquante euros (750,00 EUR)")],
    "750 euros pour les personnes de 19 ans et plus, 300 euros pour les 12 à moins de 19 ans (instruction n° 07-2026).", [["750,00 EUR", "750 EUR", "750 euros"]], domaine="change", date_ref="actuel",
    statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle", acceptables=[acc("INS-07-26", "2")],
    interdites=[forb("INS-05-25", "2", "abrogée par INS-07-26"), forb("INS-08-97", "2", "abrogée par INS-05-25")], chaine="dc")
add(T, "C_temporelle", "Quel était le montant annuel du droit de change pour voyage à l'étranger en 1998 ?", [passage("INS-08-97", "2", "quinze mille (15.000)")],
    "15 000 dinars algériens par année civile, contre-valeur en devises (instruction n° 08-97).", [["15.000", "15 000"]], domaine="change", date_ref="1998-06-30", statut="ABROGATED",
    applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne", acceptables=[acc("INS-08-97", "2")], interdites=[forb("INS-05-25", "2", "postérieure"), forb("INS-07-26", "2", "postérieure")],
    chaine="dc")
add(T, "E_abrogation", "L'instruction n° 05-2025 relative au droit de change pour voyage à l'étranger est-elle encore applicable ?",
    [passage("INS-07-26", "21", "Les dispositions de l’instruction N°05-2025 du 17 juillet 2025 relative au droit de change pour voyage à l’étranger sont abrogées", alternatives=[acc("INS-05-25", None)])],
    "Non : elle est abrogée par l'article 21 de l'instruction n° 07-2026 du 13 juillet 2026.", [["07-2026", "07-26"]], domaine="change", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="abrogation", chaine="dc")
add(T, "D_modification", "Quel texte a abrogé l'instruction n° 08-97 relative au droit de change pour voyage à l'étranger ?",
    [passage("INS-05-25", "12", "notamment celles de l’instruction N°08-97 du 28 août 1997", alternatives=[acc("INS-08-97", None)])], "L'instruction n° 05-2025 du 17 juillet 2025 (article 12).",
    [["05-2025", "05-25"]], domaine="change", date_ref="actuel", statut="ABROGATED", temporalite=True, sous_type="texte_abrogeant", chaine="dc")

# =====================================================================================================================================================
# THÈME : plafond de garantie des dépôts (REG-97-04 > REG-04-03 > REG-20-03)
# =====================================================================================================================================================
T = "gdb_plafond"
add(T, "C_temporelle", "Quel est le plafond d'indemnisation par déposant du système de garantie des dépôts bancaires ?", [passage("REG-20-03", "10", "fixé à deux millions de dinars algériens (2.000.000 DA)")],
    "2 000 000 DA par déposant, pour l'ensemble des dépôts auprès d'une même banque (règlement n° 2020-03).", [["2.000.000", "2 000 000", "deux millions"]], domaine="garantie_depots",
    date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle", acceptables=[acc("REG-20-03", "10")],
    interdites=[forb("REG-97-04", "9", "abrogé"), forb("REG-04-03", "8", "abrogé par REG-20-03")], chaine="gdb")
add(T, "C_temporelle", "Quel était le plafond d'indemnisation par déposant en 1999 ?", [passage("REG-97-04", "9", "fixé à six cents mille (600.000) Dinars Algériens")], "600 000 dinars algériens (règlement n° 97-04).",
    [["600.000", "600 000", "six cents mille"]], domaine="garantie_depots", date_ref="1999-06-30", statut="ABROGATED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("REG-97-04", "9")], interdites=[forb("REG-20-03", "10", "postérieur"), forb("REG-18-01", "5", "postérieur")], chaine="gdb")
add(T, "E_abrogation", "Le règlement n° 97-04 relatif au système de garantie des dépôts bancaires est-il encore applicable ?",
    [passage("REG-04-03", "20", "Les dispositions du règlement n°97-04 du 2 Ramadhan 1418 correspondant au 31 décembre 1997, susvisé, sont abrogées", alternatives=[acc("REG-97-04", None)])],
    "Non : il est abrogé par le règlement n° 2004-03 (article 20).", [["04-03", "2004-03"]], domaine="garantie_depots", date_ref="actuel", statut="ABROGATED", temporalite=True,
    sous_type="abrogation", chaine="gdb")

# =====================================================================================================================================================
# SÉRIE PÉRIODIQUE : prime due au fonds de garantie des dépôts (un texte par exercice ; les valeurs NE s'abrogent PAS entre elles)
# =====================================================================================================================================================
T = "prime_gdb"
PRIME = ["INS-09-00", "INS-05-02", "INS-03-03", "INS-04-04", "INS-05-05", "INS-04-06", "INS-07-07", "INS-05-08", "INS-04-09", "INS-03-10", "INS-06-11", "INS-02-12", "INS-03-13", "INS-02-14",
         "INS-01-16", "INS-10-16", "INS-02-18", "INS-04-18", "INS-03-19", "INS-13-20", "INS-01-23", "INS-01-24", "INS-07-25"]


def other_periods(keep, art="2"):
    return [forb(w, art, "autre exercice de la série (valable pour sa propre période, pas pour celle demandée)") for w in PRIME if w != keep]


add(T, "C_temporelle", "Quel est le taux de la prime due au fonds de garantie des dépôts bancaires pour l'exercice 2004 ?", [passage("INS-05-05", "2", "fixé pour l’exercice 2004")],
    "0,30 % de l'ensemble des dépôts enregistrés au 31 décembre (instruction n° 05-2005 du 16 juin 2005).", [["0,30%", "0,30 %", "0,3%"]], domaine="garantie_depots", date_ref="exercice 2004",
    statut="HISTORICAL", applicable_a_la_date=True, temporalite=True, sous_type="serie_periode", acceptables=[acc("INS-05-05", "2")], interdites=other_periods("INS-05-05"), chaine="prime")
add(T, "C_temporelle", "Quel est le taux de la prime due au fonds de garantie des dépôts bancaires pour l'exercice 2022 ?", [passage("INS-01-24", "2", "fixé pour l’exercice 2022")],
    "0,15 % (instruction n° 01-2024 du 18 janvier 2024).", [["0,15%", "0,15 %"]], domaine="garantie_depots", date_ref="exercice 2022", statut="HISTORICAL", applicable_a_la_date=True,
    temporalite=True, sous_type="serie_periode", difficulte="difficile", acceptables=[acc("INS-01-24", "2")], interdites=other_periods("INS-01-24"), chaine="prime")
add(T, "C_temporelle", "Quel est le taux de la prime due au fonds de garantie des dépôts bancaires pour l'exercice 2021 ?", [passage("INS-01-23", "2", "fixé pour les exercices 2020 et 2021")],
    "0,1 % (instruction n° 01-2023, qui fixe le taux pour les exercices 2020 et 2021).", [["0,1%", "0,1 %"]], domaine="garantie_depots", date_ref="exercice 2021", statut="HISTORICAL",
    applicable_a_la_date=True, temporalite=True, sous_type="serie_periode", difficulte="difficile", acceptables=[acc("INS-01-23", "2")], interdites=other_periods("INS-01-23"), chaine="prime")
add(T, "C_temporelle", "Quel est le dernier taux de la prime due au fonds de garantie des dépôts bancaires publié ?", [passage("INS-07-25", "2", "fixé pour l’exercice 2023")],
    "0,1 % pour l'exercice 2023 (instruction n° 07-2025 du 28 août 2025) ; c'est la dernière période publiée dans le corpus.", [["0,1%", "0,1 %"]], domaine="garantie_depots", date_ref="actuel",
    statut="ACTIVE", temporalite=True, sous_type="serie_derniere", acceptables=[acc("INS-07-25", "2")], interdites=other_periods("INS-07-25"), chaine="prime",
    note="Série périodique : « actuel » = dernière période publiée ; le corpus ne prouve pas qu'aucune instruction plus récente n'existe.")
add(T, "C_temporelle", "Jusqu'à quelle date les banques devaient-elles verser la prime au fonds de garantie des dépôts bancaires due pour l'exercice 2012 ?", [passage("INS-03-13", "3", "au plus tard le 15 décembre 2013")],
    "Au plus tard le 15 décembre 2013 (instruction n° 03-2013 du 19 novembre 2013, qui fixe le taux de l'exercice 2012).", [["15 décembre 2013"]], domaine="garantie_depots", date_ref="exercice 2012",
    statut="HISTORICAL", applicable_a_la_date=True, temporalite=True, sous_type="serie_periode", difficulte="difficile", acceptables=[acc("INS-03-13", "3")], interdites=other_periods("INS-03-13", "3"),
    chaine="prime", note="Piège : l'instruction n° 02-2012 (20 novembre 2012) vise l'exercice 2011, pas 2012.")

# =====================================================================================================================================================
# SÉRIE PÉRIODIQUE : seuils semestriels des taux d'intérêt excessifs (le numéro/année de la note n'est PAS la période visée)
# =====================================================================================================================================================
T = "taux_excessifs"
add(T, "C_temporelle", "Quelle note de la Banque d'Algérie fixe les seuils des taux d'intérêt excessifs applicables au premier semestre 2024 ?", [passage("NOT-02-23", None, "applicables au titre du premier semestre 2024")],
    "La note aux banques n° 02-2023 (elle fixe les seuils au titre du premier semestre 2024).", [["02-2023", "02 - 2023", "02-23"]], domaine="taux_excessifs", date_ref="premier semestre 2024", statut="HISTORICAL",
    applicable_a_la_date=True, temporalite=True, sous_type="serie_periode", difficulte="difficile", acceptables=[acc("NOT-02-23", None)],
    interdites=[forb("NOT-01-24", None, "deuxième semestre 2024"), forb("NOT-01-23", None, "deuxième semestre 2023"), forb("NOT-02-24-20160901", None, "premier semestre 2025")], chaine="excessifs",
    note="Piège : le millésime du numéro de la note (2023) est celui de l'année de publication, pas du semestre visé (2024).")
add(T, "C_temporelle", "Pour quel semestre la note aux banques n° 01-2025 fixe-t-elle les seuils des taux d'intérêt excessifs ?", [passage("NOT-01-25", None, "applicables au titre du deuxième semestre 2025")],
    "Pour le deuxième semestre 2025.", [["deuxième semestre 2025"]], domaine="taux_excessifs", date_ref="actuel", statut="HISTORICAL", temporalite=True, sous_type="serie_periode",
    acceptables=[acc("NOT-01-25", None)], chaine="excessifs")


# =====================================================================================================================================================
# THÈME : délai de rapatriement des recettes d'exportation (REG-07-01 art. 61 : 120 j -> 180 j -> 360 j -> 120 j) — la valeur remonte puis REDESCEND
# =====================================================================================================================================================
T = "rapatriement"
R07 = passage("REG-07-01", "61", "dans un délai n'excédant pas cent vingt (120) jours")
R11 = passage("REG-11-06", "2", "dans un délai n'excédant pas cent quatre-vingt (180) jours", alternatives=[acc("REG-11-06", "2")])
R16 = passage("REG-16-04", "2", "dans un délai fixé à trois cent soixante (360) jours")
R26 = passage("REG-26-02", "2", "dans un délai n'excédant pas cent vingt (120) jours")
ALLR = {"07": forb("REG-07-01", "61", "version d'origine remplacée"), "11": forb("REG-11-06", "2", "remplacée en 2016"), "11b": forb("REG-11-06", "2", "doublon daté 2007, remplacé en 2016"),
        "16": forb("REG-16-04", "2", "remplacée en 2026"), "26": forb("REG-26-02", "2", "postérieure")}
add(T, "C_temporelle", "Dans quel délai l'exportateur doit-il rapatrier la recette d'une exportation hors hydrocarbures ?", [R26],
    "120 jours à compter de la date d'expédition (biens) ou de réalisation (services) — règlement n° 26-02 du 23 juillet 2026, qui réécrit l'article 61 du règlement n° 07-01.",
    [["cent vingt (120) jours", "120 jours", "cent vingt jours"]], domaine="change", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="valeur_actuelle",
    acceptables=[acc("REG-26-02", "2")], interdites=[ALLR["07"], ALLR["11"], ALLR["11b"], ALLR["16"]], chaine="rapatriement",
    note="Piège : 120 jours est aussi la valeur d'origine (2007) ; la bonne source est le texte de 2026, pas celui de 2007.")
add(T, "C_temporelle", "Quel était le délai de rapatriement des recettes d'exportation hors hydrocarbures en 2013 ?", [R11], "180 jours (règlement n° 2011-06).",
    [["cent quatre-vingt (180) jours", "180 jours"]], domaine="change", date_ref="2013-06-30", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("REG-11-06", "2"), acc("REG-11-06", "2")], interdites=[ALLR["07"], ALLR["16"], ALLR["26"]], chaine="rapatriement")
add(T, "C_temporelle", "Quel était le délai de rapatriement des recettes d'exportation hors hydrocarbures au 1er mars 2018 ?", [R16], "360 jours (règlement n° 2016-04).",
    [["trois cent soixante (360) jours", "360 jours"]], domaine="change", date_ref="2018-03-01", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    difficulte="difficile", acceptables=[acc("REG-16-04", "2")], interdites=[ALLR["07"], ALLR["11"], ALLR["11b"], ALLR["26"]], chaine="rapatriement")
add(T, "C_temporelle", "Quel était le délai de rapatriement des recettes d'exportation en 2008 ?", [R07], "120 jours (règlement n° 07-01, version d'origine).",
    [["cent vingt (120) jours", "120 jours"]], domaine="change", date_ref="2008-06-30", statut="REPLACED", applicable_a_la_date=True, temporalite=True, sous_type="valeur_ancienne",
    acceptables=[acc("REG-07-01", "61")], interdites=[ALLR["11"], ALLR["11b"], ALLR["16"], ALLR["26"]], chaine="rapatriement")
add(T, "D_modification", "Quel règlement a porté à 360 jours le délai de rapatriement des recettes d'exportation hors hydrocarbures ?", [R16], "Le règlement n° 2016-04 du 17 novembre 2016 (article 2).",
    [["2016-04", "16-04"]], domaine="change", date_ref="actuel", statut="REPLACED", temporalite=True, sous_type="texte_modificateur", chaine="rapatriement")
add(T, "F_comparaison", "Quelle différence entre le délai de rapatriement fixé par le règlement n° 2016-04 et celui fixé par le règlement n° 26-02 ?", [R16, R26],
    "360 jours en 2016 ; 120 jours depuis le règlement n° 26-02 de 2026.", [["360"], ["120"]], domaine="change", date_ref="actuel", statut="ACTIVE", temporalite=True, mode="all",
    sous_type="ancien_vs_actuel", difficulte="difficile", chaine="rapatriement")
add(T, "B_multi_textes", "Quels règlements ont successivement modifié l'article 61 du règlement n° 07-01 sur le délai de rapatriement des recettes d'exportation ?", [R11, R16, R26],
    "Les règlements n° 2011-06, n° 2016-04 et n° 26-02.", [["2011-06", "11-06"], ["2016-04", "16-04"], ["26-02"]], domaine="change", date_ref="actuel", statut="ACTIVE", temporalite=True,
    mode="all", difficulte="difficile", chaine="rapatriement")

# =====================================================================================================================================================
# QUESTIONS DE MODIFICATION (D) hors chaînes ci-dessus
# =====================================================================================================================================================
add("mod_taux_excessifs", "D_modification", "Quelle instruction a modifié l'article 2 de l'instruction n° 08-2016 relative aux modalités de fixation des taux excessifs ?",
    [passage("INS-06-26", "2", "L’article 2 de l’instruction n°08-2016 du premier septembre 2016 relative aux modalités de fixation des taux excessifs est modifié et rédigé comme suit")],
    "L'instruction n° 06-2026 (article 2 : crédit à taux excessif = taux effectif global excédant de plus de 5 % le taux moyen du semestre précédent).", [["06-2026", "06-26"]],
    domaine="taux_excessifs", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur")
add("mod_escompte", "D_modification", "Quel règlement a complété l'article 11 du règlement n° 15-01 relatif aux opérations d'escompte et de réescompte ?",
    [passage("REG-16-03", "6", "L’article 11 du règlement n°15-01 susvisé, est complété et rédigé comme suit")], "Le règlement n° 2016-03 du 28 juillet 2016 (article 6).", [["16-03", "2016-03"]],
    domaine="refinancement", date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur")
add("mod_engagements", "D_modification", "Quelle instruction a modifié et complété l'instruction n° 02-2015 fixant le niveau des engagements extérieurs des banques ?",
    [passage("INS-03-26", "1", "modifier et compléter l’instruction n°02-2015 du 22 juillet 2015")], "L'instruction n° 03-2026 du 26 avril 2026.", [["03-2026", "03-26"]], domaine="prudentiel",
    date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur")
add("mod_change", "D_modification", "Quel règlement du 28 mars 2021 modifie et complète le règlement n° 07-01 relatif aux transactions courantes avec l'étranger ?",
    [passage("REG-21-01", "1", "modifier et de compléter le règlement n°07-01 du 15 Moharram 1428")], "Le règlement n° 21-01.", [["21-01"]], domaine="change", date_ref="actuel", statut="ACTIVE",
    temporalite=True, sous_type="texte_modificateur")
add("mod_effets", "D_modification", "Quelle instruction a complété l'article 3 de l'instruction n° 02-2016 relative aux opérations d'escompte d'effets publics ?",
    [passage("INS-02-17", "2", "L’article 3 de l’instruction n° 02-2016 ci-dessus citée est complété comme suit")], "L'instruction n° 02-2017.", [["02-2017", "02-17"]], domaine="refinancement",
    date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur")
add("mod_74", "D_modification", "Quelle instruction a ajouté un article 2 bis à l'instruction n° 74-94 relative aux règles prudentielles de gestion des banques ?",
    [passage("INS-09-07", "2", "est complété par un article 2 bis rédigé comme suit")], "L'instruction n° 09-2007 du 25 octobre 2007.", [["09-2007", "09-07"]], domaine="prudentiel",
    date_ref="actuel", statut="ACTIVE", temporalite=True, sous_type="texte_modificateur", difficulte="difficile")

# =====================================================================================================================================================
# QUESTIONS MULTI-TEXTES (B) et COMPARAISONS (F) — chaînes déjà introduites
# =====================================================================================================================================================
add("gdb_plafond", "B_multi_textes", "Quels règlements ont successivement fixé le plafond d'indemnisation par déposant du système de garantie des dépôts ?",
    [passage("REG-97-04", "9", "fixé à six cents mille (600.000) Dinars Algériens"), passage("REG-04-03", "8", "fixé à six cent mille dinars (600.000 DA)"),
     passage("REG-20-03", "10", "fixé à deux millions de dinars algériens (2.000.000 DA)")],
    "Les règlements n° 97-04 (600 000 DA), n° 2004-03 (600 000 DA) puis n° 2020-03 (2 000 000 DA).", [["97-04"], ["2004-03", "04-03"], ["2020-03", "20-03"]], domaine="garantie_depots", date_ref="actuel",
    statut="ACTIVE", temporalite=True, mode="all", difficulte="difficile", chaine="gdb")
add("gdb_plafond", "F_comparaison", "Quelle différence entre le plafond d'indemnisation du règlement n° 97-04 et celui du règlement n° 2020-03 ?",
    [passage("REG-97-04", "9", "fixé à six cents mille (600.000) Dinars Algériens"), passage("REG-20-03", "10", "fixé à deux millions de dinars algériens (2.000.000 DA)")],
    "600 000 DA sous le règlement 97-04 ; 2 000 000 DA sous le règlement 2020-03.", [["600.000", "600 000"], ["2.000.000", "2 000 000"]], domaine="garantie_depots", date_ref="actuel", statut="ACTIVE",
    temporalite=True, mode="all", sous_type="ancien_vs_actuel", chaine="gdb")
add("dc_voyage", "B_multi_textes", "Quelles instructions ont successivement fixé le droit de change pour voyage à l'étranger ?",
    [passage("INS-08-97", "2", "quinze mille (15.000)"), passage("INS-05-25", "2", "sept cent cinquante euros (750,00 EUR)"), passage("INS-07-26", "2", "sept cent cinquante euros (750,00 EUR)")],
    "Les instructions n° 08-97, n° 05-2025 puis n° 07-2026.", [["08-97"], ["05-2025", "05-25"], ["07-2026", "07-26"]], domaine="change", date_ref="actuel", statut="ACTIVE", temporalite=True,
    mode="all", difficulte="difficile", chaine="dc")
add("dc_voyage", "F_comparaison", "Quelle différence entre le droit de change pour voyage de l'instruction n° 08-97 et celui de l'instruction n° 07-2026 ?",
    [passage("INS-08-97", "2", "quinze mille (15.000)"), passage("INS-07-26", "2", "sept cent cinquante euros (750,00 EUR)")],
    "15 000 dinars par année civile (contre-valeur en devises) en 1997 ; 750 euros pour les 19 ans et plus (300 euros de 12 à 19 ans) depuis 2026.", [["15.000", "15 000"], ["750"]], domaine="change",
    date_ref="actuel", statut="ACTIVE", temporalite=True, mode="all", sous_type="ancien_vs_actuel", chaine="dc")
add("taux_directeur", "B_multi_textes", "Quelles instructions ont successivement fixé le taux d'intérêt directeur de refinancement depuis 2020 ?", [D20, D25, D26],
    "Les instructions n° 07-2020 (3 %), n° 08-2025 (2,75 %) et n° 02-2026 (2,50 %).", [["07-2020", "07-20"], ["08-2025", "08-25"], ["02-2026", "02-26"]], domaine="politique_monetaire",
    date_ref="actuel", statut="ACTIVE", temporalite=True, mode="all", difficulte="difficile", chaine="taux_dir")
add("reserves", "F_comparaison", "Quelle différence entre le taux des réserves obligatoires de 2013 et le taux actuel ?",
    [passage("INS-02-13", "2", "Le taux des réserves obligatoires est fixé à 12 % de l'assiette"), passage("INS-01-26", "2", "Le taux des réserves obligatoires est fixé à 1% de l'assiette")],
    "12 % en 2013 (instruction n° 02-2013) ; 1 % aujourd'hui (instruction n° 01-2026).", [["12 %", "12%"], ["1%", "1 %"]], domaine="politique_monetaire", date_ref="actuel", statut="ACTIVE", temporalite=True,
    mode="all", sous_type="ancien_vs_actuel", chaine="reserves")
add("reescompte", "F_comparaison", "Quelle différence entre le taux de réescompte de 1998 et le taux de réescompte actuel ?",
    [passage("INS-01-98", None, "le taux de réescompte est fixé à 9,5 %"), passage("INS-03-17", None, "le taux de réescompte est fixé à 3,75 %")],
    "9,5 % en 1998 (instruction n° 01-98) ; 3,75 % depuis 2017 (instruction n° 03-2017).", [["9,5"], ["3,75"]], domaine="politique_monetaire", date_ref="actuel", statut="ACTIVE", temporalite=True,
    mode="all", sous_type="ancien_vs_actuel", chaine="reescompte")
add("lbc_ft", "B_multi_textes", "Quels règlements ont successivement organisé la prévention et la lutte contre le blanchiment d'argent dans les banques ?",
    [passage("REG-05-05", "1", "en application de la Loi n°05-01 du 27 Dhou El Hidja 1425"), passage("REG-12-03", "1", "en application de la loi n° 05-01 du 27 Dhou El Hidja 1425"),
     passage("REG-24-03", "9", "doivent développer et appliquer des politiques et des procédures relatives à la")],
    "Les règlements n° 2005-05, n° 2012-03 puis n° 24-03 (lui-même modifié ensuite par le règlement n° 25-14).", [["2005-05", "05-05"], ["2012-03", "12-03"], ["24-03"]], domaine="lbc_ft", date_ref="actuel",
    statut="MODIFIED", temporalite=True, mode="all", difficulte="difficile", chaine="lbc")
add("prudentiel_2014", "B_multi_textes", "Quels règlements de 2014 fixent respectivement les coefficients de solvabilité et les règles de division des risques ?",
    [passage("REG-14-01", "1", "fixer les coefficients de solvabilité applicables aux banques et établissements financiers"),
     passage("REG-14-02", "1", "définir les règles que les banques et établissements financiers doivent observer en matière de division des risques")],
    "Le règlement n° 14-01 (coefficients de solvabilité) et le règlement n° 14-02 (division des risques et participations).", [["14-01"], ["14-02"]], domaine="prudentiel", date_ref=None,
    statut="UNKNOWN", mode="all", difficulte="moyen")
add("banque_digitale", "B_multi_textes", "Quels règlements définissent la banque digitale et fixent son capital minimum ?",
    [passage("REG-24-04", "2", "toute banque offrant des services et produits bancaires exclusivement via des canaux"), passage("REG-24-02", "2", "c. Banque digitale : dix milliards de dinars algériens")],
    "Le règlement n° 24-04 (définition) et le règlement n° 24-02 (capital minimum de 10 milliards de dinars).", [["24-04"], ["24-02"]], domaine="banque_digitale", date_ref="actuel", statut="ACTIVE",
    mode="all", difficulte="difficile")

# =====================================================================================================================================================
# QUESTIONS D'ABROGATION (E) supplémentaires — dont un texte MODIFIÉ mais non abrogé
# =====================================================================================================================================================
add("abr_92_04", "E_abrogation", "Le règlement n° 92-04 relatif au contrôle des changes est-il encore applicable ?",
    [passage("REG-95-07", "43", "Les dispositions du règlement n°92-04 du 22 mars 1992 relatif au contrôle des changes ainsi que toutes celles contraires au présent règlement sont abrogées", alternatives=[acc("REG-92-04", None)])],
    "Non : il est abrogé par le règlement n° 95-07 du 23 décembre 1995 (article 43), qui le modifie et le remplace.", [["95-07"]], domaine="change", date_ref="actuel", statut="REPLACED", temporalite=True,
    sous_type="abrogation")
add("abr_07_01", "E_abrogation", "Le règlement n° 07-01 relatif aux règles applicables aux transactions courantes avec l'étranger est-il encore applicable ?",
    [passage("REG-26-02", "1", "modifier et de compléter le règlement n° 07-01 du 15 Moharram 1428", alternatives=[acc("REG-07-01", None)])],
    "Il n'est pas abrogé : il a été modifié et complété à plusieurs reprises (notamment par les règlements n° 21-01 et n° 26-02) ; son état actuel doit se lire avec ces modifications.",
    [["modifié"]], domaine="change", date_ref="actuel", statut="MODIFIED", temporalite=True, sous_type="texte_modifie_non_abroge", difficulte="difficile")


# =====================================================================================================================================================
# QUESTIONS DIRECTES supplémentaires (suite du tirage)
# =====================================================================================================================================================
direct("emv", "À quel standard international la carte bancaire doit-elle répondre selon l'instruction n° 12-2020 ?", "INS-12-20", "2", "doit répondre par ailleurs au standard EMV",
       "Aux normes internationales du tableau annexé et au standard EMV (Europay - Mastercard - Visa).", [["EMV"]], "moyens_de_paiement", "obligation", "ACTIVE")
direct("campagne", "Qui est le seul signataire du compte bancaire ouvert pour une campagne électorale ?", "INS-05-21", "2", "demeure le seul et exclusif signataire",
       "Le trésorier de campagne électorale, qui ne peut déléguer sa signature, même au candidat.", [["trésorier de campagne"]], "comptes", "obligation", "UNKNOWN", "moyen")
direct("garfonds", "Les fonds rapatriés au titre de la mise en jeu d'un acte de garantie peuvent-ils être versés au crédit d'un compte devises ?", "INS-05-94", "13",
       "ne peuvent être versés au crédit d'un compte devises, sauf dans le cas où les engagements contractuels", "Non, sauf si les engagements contractuels ont été réalisés à partir d'un compte devises.",
       [["ne peuvent être versés"]], "change", "interdiction", "UNKNOWN", "difficile")
direct("trinv", "Sur présentation de quels documents le transfert de fonds pour un investissement à l'étranger peut-il intervenir ?", "INS-03-02", "4",
       "ne peut intervenir que sur présentation par l'opérateur économique de droit algérien", "Sur présentation d'une demande de transfert signée par l'organe de gestion habilité et de l'autorisation d'investissement à l'étranger du Conseil.",
       [["demande de transfert"], ["autorisation d'investissement", "autorisation d’investissement"]], "investissement_etranger", "procedure", "UNKNOWN", "moyen")

# =====================================================================================================================================================
# QUESTIONS AMBIGUËS (G) — le système doit demander une précision
# =====================================================================================================================================================
for n, q in enumerate(["Quel est le montant maximum ?", "Quelle est la date limite ?", "Quels documents faut-il fournir ?", "Que dit l'article 3 ?", "Le texte est-il encore applicable ?",
          "Quelle est la différence entre l'ancien et le nouveau régime ?", "Quelles sanctions sont prévues ?", "Quelle est la procédure à suivre ?"]):
    clarify(f"ambigu_{n}", q, "general")

# =====================================================================================================================================================
# QUESTIONS HORS CORPUS (H) — sujet vérifié ABSENT de tous les passages (FR + AR) ; domaines voisins du droit/finance mais hors Banque d'Algérie
# =====================================================================================================================================================
for n, (q, pat) in enumerate([("Quel est le taux de la taxe sur l'activité professionnelle ?", r"taxe sur l.activit[ée] professionnelle|\bTAP\b"),
               ("Quel est le montant de l'amende pour excès de vitesse ?", r"exc[èe]s de vitesse"),
               ("Quel est le montant de l'allocation familiale mensuelle ?", r"allocations? familiales?"),
               ("Quelle est la durée du mandat du Président de la République ?", r"mandat du pr[ée]sident"),
               ("Quel est le taux directeur de la Banque centrale européenne ?", r"Banque centrale europ[ée]enne|\bBCE\b"),
               ("Comment obtenir un visa pour la France ?", r"visa (pour|schengen)"),
               ("À quel âge peut-on partir à la retraite en Algérie ?", r"[âa]ge (l[ée]gal )?de (la )?retraite"),
               ("Quelle est la procédure de divorce ?", r"divorce"),
               ("Quelles sont les conditions pour obtenir un permis de port d'arme ?", r"port d.arme"),
               ("Quelle est la durée du service militaire obligatoire ?", r"service militaire")]):
    refuse(f"hors_corpus_{n}", "H_hors_corpus", q, "hors_corpus", absent=pat)

# =====================================================================================================================================================
# QUESTIONS HORS SUJET (I) — le système doit refuser
# =====================================================================================================================================================
for n, q in enumerate(["Quelle est la capitale du Japon ?", "Qui a gagné la Coupe du monde de football en 2018 ?", "Donne-moi une recette de couscous.", "Quelle est la vitesse de la lumière ?",
          "Écris un poème sur l'automne.", "Traduis « merci » en espagnol."]):
    refuse(f"hors_sujet_{n}", "I_hors_sujet", q, "hors_sujet")


# =====================================================================================================================================================
# QUESTIONS FR / AR (J) — question en ARABE, passage attendu = le même article (texte arabe OCR ou texte français : le classement compare (texte, article), pas la langue) ;
# chaque question arabe est APPARIÉE à une question française du même concept (`paire_fr_question`) pour comparer les deux langues. Même split que le jumeau français.
# =====================================================================================================================================================
def ar(theme, q, work, art, fr_quote, answer, facts, twin, domaine, statut=None, date_ref=None, **kw):
    it = add(theme, "J_fr_ar", q, [passage(work, art, fr_quote)], answer, facts, domaine=domaine, langue="ar", sous_type="question_arabe", statut=statut, date_ref=date_ref,
             difficulte="moyen", note="question arabe appariée à une question française du même concept ; passage cité en français (même article)", **kw)
    it["paire_fr_question"] = twin
    return it


ar("gdb_plafond", "ما هو الحد الأقصى للتعويض الممنوح لكل مودع في نظام ضمان الودائع المصرفية؟", "REG-20-03", "10", "fixé à deux millions de dinars algériens (2.000.000 DA)",
   "مليونا دينار جزائري (2.000.000 دج) لكل مودع (النظام رقم 2020-03).", [["2.000.000", "2 000 000", "2000000", "مليوني", "مليونا"]],
   "Quel est le plafond d'indemnisation par déposant du système de garantie des dépôts bancaires ?", "garantie_depots", statut="ACTIVE", date_ref="actuel", temporalite=True,
   acceptables=[acc("REG-20-03", "10")], interdites=[forb("REG-97-04", "9", "abrogé"), forb("REG-04-03", "8", "abrogé par REG-20-03")], chaine="gdb")
ar("direct_ie26", "ما هو الحد الأقصى لمستوى الالتزامات الخارجية بالتوقيع للبنوك والمؤسسات المالية؟", "INS-03-26", "2", "ne doit dépasser cinquante pourcent (50%) de leurs fonds propres",
   "خمسون بالمئة (50%) من أموالها الخاصة القانونية.", [["50%", "50 %", "50", "خمسين", "خمسون"]],
   "Quel est le niveau maximal des engagements extérieurs par signature des banques et établissements financiers ?", "prudentiel")
ar("lbc_ft", "ماذا يجب على المؤسسات الخاضعة فعله إذا لم تتمكن من التعرف على هوية زبونها والتحقق منها؟", "REG-24-03", "19", "doivent s’abstenir d’ouvrir un compte, d’établir des relations d'affaires",
   "الامتناع عن فتح الحساب أو إقامة علاقة أعمال أو إجراء العملية، أو إنهاء علاقة الأعمال.", [["الامتناع", "s’abstenir", "s'abstenir"]],
   "Que doivent faire les institutions assujetties si elles ne parviennent pas à identifier et vérifier l'identité de leur client ?", "lbc_ft")
ar("direct_fict", "ما هو التزام المؤسسات الخاضعة تجاه البنوك الصورية؟", "INS-03-24", "25", "sont tenues de s’abstenir d’établir ou de maintenir toute relation de correspondance bancaire",
   "الامتناع عن إقامة أو الحفاظ على أي علاقة مراسلة مصرفية مع البنوك الصورية.", [["الامتناع", "s’abstenir", "s'abstenir"]],
   "Quelle obligation les institutions assujetties ont-elles à l'égard des banques fictives ?", "lbc_ft")
ar("direct_islam", "ما المقصود بالعملية البنكية المتعلقة بالصيرفة الإسلامية؟", "REG-20-02", "2", "toute opération de banque qui ne donne pas lieu à la perception ou au versement d’intérêts",
   "كل عملية بنكية لا يترتب عنها تحصيل أو تسديد الفوائد.", [["لا يترتب عنها تحصيل أو تسديد الفوائد", "ne donne pas lieu à la perception ou au versement d’intérêts", "ne donne pas lieu à la perception ou au versement d'intérêts"]],
   "Qu'est-ce qu'une opération de banque relevant de la finance islamique selon le règlement n° 20-02 ?", "finance_islamique")
ar("direct_cdev", "هل يمكن أن تكون الحسابات بالعملة الصعبة المفتوحة باسم الأشخاص المذكورين مدينة؟", "REG-09-01", "4", "ne peuvent en aucun cas présenter un solde débiteur",
   "لا، يجب أن تعمل هذه الحسابات حصرا في وضعية دائنة ولا يمكن أن تكون مدينة بأي حال.", [["situation créditrice", "دائنة", "ولا يمكن بأي حال"]],
   "Un compte devises ouvert au nom des personnes visées par le règlement 2009-01 peut-il être débiteur ?", "change")
ar("direct_campagne", "من هو الموقّع الوحيد على الحساب البنكي الخاص بالحملة الانتخابية؟", "INS-05-21", "2", "demeure le seul et exclusif signataire",
   "الأمين المالي للحملة الانتخابية، ولا يمكنه تفويض التوقيع.", [["trésorier de campagne", "الأمين المالي"]],
   "Qui est le seul signataire du compte bancaire ouvert pour une campagne électorale ?", "comptes")
ar("capital_minimum", "ما هو الحد الأدنى لرأسمال البنوك في سنة 2005؟", "REG-04-01", "2", "deux milliards cinq cent millions de dinars (2.500.000.000 DA) pour les banques",
   "2,5 مليار دينار جزائري (النظام رقم 2004-01).", [["2.500.000.000", "2 500 000 000", "2,5", "مليارين وخمسمائة مليون", "مليارين وخمسماتة مليون"]],
   "Quel était le capital minimum d'une banque en 2005 ?", "prudentiel", statut="ABROGATED", date_ref="2005-06-30", applicable_a_la_date=True, temporalite=True,
   acceptables=[acc("REG-04-01", "2")], interdites=[forb("REG-90-01-19900704", "1", "abrogé en 2004"), forb("REG-08-04", "2", "postérieur"), forb("REG-18-03", "2", "postérieur"), forb("REG-24-02", "2", "postérieur")],
   chaine="cap_min")
ar("reserves", "ما هو معدل الاحتياطيات الإجبارية المعمول به حاليا؟", "INS-01-26", "2", "Le taux des réserves obligatoires est fixé à 1% de l'assiette",
   "1% من وعاء الاحتياطيات (التعليمة رقم 01-2026).", [["1%", "1 %", "1٪", "1"]], "Quel est le taux des réserves obligatoires actuellement fixé ?", "politique_monetaire",
   statut="ACTIVE", date_ref="actuel", temporalite=True, acceptables=[acc("INS-01-26", "2")], interdites=others("INS-01-26"), chaine="reserves")
ar("direct_exp15", "في أي أجل يمكن أن يتم التوطين المصرفي لصادرات المنتجات الطازجة والقابلة للتلف و/أو الخطيرة؟", "INS-07-21", "2", "durant les quinze (15) jours ouvrés qui suivent la date d’expédition",
   "خلال خمسة عشر (15) يوم عمل التي تلي تاريخ الشحن والتصريح الجمركي.", [["15", "quinze (15) jours ouvrés", "خمسة عشر"]],
   "Dans quel délai la domiciliation des exportations de produits frais, périssables ou dangereux peut-elle avoir lieu ?", "change")
ar("direct_cdb", "ما الذي يجب على البنوك والمؤسسات المالية إبلاغ زبائنها والجمهور به؟", "REG-94-13", "6", "tenus de porter à la connaissance de leur clientèle et du public les conditions de banque qu'ils pratiquent",
   "الشروط التي تطبقها على عملياتها (شروط البنك).", [["conditions de banque", "الشروط"]],
   "Que doivent porter à la connaissance de leur clientèle les banques et établissements financiers ?", "conditions_banque")
ar("prime_gdb", "إلى أي تاريخ يجب دفع العلاوة لصندوق ضمان الودائع المصرفية المستحقة بعنوان سنة 2012؟", "INS-03-13", "3", "au plus tard le 15 décembre 2013",
   "في أجل أقصاه 15 ديسمبر 2013 (التعليمة رقم 03-2013).", [["15 décembre 2013", "15 ديسمبر 2013", "15 ديسمير 2013", "15 ديسمبر"]], "Jusqu'à quelle date les banques devaient-elles verser la prime au fonds de garantie des dépôts bancaires due pour l'exercice 2012 ?",
   "garantie_depots", statut="HISTORICAL", date_ref="exercice 2012", applicable_a_la_date=True, temporalite=True, acceptables=[acc("INS-03-13", "3")], interdites=other_periods("INS-03-13", "3"), chaine="prime")
ar("taux_directeur", "ما هو معدل الفائدة التوجيهي المطبق على عمليات إعادة التمويل الرئيسية؟", "INS-02-26", "2", "est fixé à 2,50%",
   "2,50% (التعليمة رقم 02-2026).", [["2,50%", "2,50 %", "2,5", "2.5", "2,50"]], "Quel est le taux d'intérêt directeur applicable aux opérations principales de refinancement ?", "politique_monetaire",
   statut="ACTIVE", date_ref="actuel", temporalite=True, acceptables=[acc("INS-02-26", "2")], interdites=[forb("INS-08-25", "2", "remplacé par INS-02-26"), forb("INS-07-20", "2", "remplacé")], chaine="taux_dir")
ar("gdb_plafond", "ما هو سقف التعويض لكل مودع في سنة 1999؟", "REG-97-04", "9", "fixé à six cents mille (600.000) Dinars Algériens",
   "ستمائة ألف (600.000) دينار جزائري (النظام رقم 97-04).", [["600.000", "600 000", "ستمائة ألف", "ستمّائة ألف"]], "Quel était le plafond d'indemnisation par déposant en 1999 ?", "garantie_depots",
   statut="ABROGATED", date_ref="1999-06-30", applicable_a_la_date=True, temporalite=True, acceptables=[acc("REG-97-04", "9")],
   interdites=[forb("REG-20-03", "10", "postérieur"), forb("REG-18-01", "5", "postérieur")], chaine="gdb")


TEST_FRACTION = 0.38


def assign_splits():
    """DEV / TEST par THÈME (tous les items d'un thème dans le même split), glouton stratifié par type, graine fixe ; décidé sans regarder le comportement du système."""
    by_theme = {}
    for t, it in ITEMS:
        by_theme.setdefault(t, []).append(it)
    n_type = Counter(it["type_de_question"] for _, it in ITEMS)
    tgt = {k: v * TEST_FRACTION for k, v in n_type.items()}
    cur = Counter()
    themes = sorted(by_theme)
    random.Random(SEED).shuffle(themes)
    for th in themes:
        cnt = Counter(it["type_de_question"] for it in by_theme[th])
        gain = sum(min(c, max(0.0, tgt[k] - cur[k])) - max(0.0, cur[k] + c - tgt[k] - 0.5) for k, c in cnt.items())
        split = "TEST" if gain > 0 else "DEV"
        for it in by_theme[th]:
            it["split"] = split
        if split == "TEST":
            cur.update(cnt)
    return by_theme


def finalize(out_path):
    by_theme = assign_splits()
    order = {t: i for i, t in enumerate(["A_direct", "B_multi_textes", "C_temporelle", "D_modification", "E_abrogation", "F_comparaison", "G_ambigue", "H_hors_corpus", "I_hors_sujet", "J_fr_ar"])}
    items = [it for _, it in ITEMS]
    items.sort(key=lambda it: (order[it["type_de_question"]], it["redaction"]["theme"], it["question"]))
    for n, it in enumerate(items, 1):
        it["id"] = f"H{n:03d}"
    by_q = {it["question"]: it["id"] for it in items}
    for it in items:
        if it.get("paire_fr_question"):
            it["paire_fr_id"] = by_q[it["paire_fr_question"]]            # jumeau français du même concept (comparaison FR / AR)
    bad = 0
    for it in items:
        pb = verify_item(it, CORPUS)
        if pb:
            bad += 1
            print(it["id"], "|", it["question"][:60], "|", "; ".join(pb))
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    import hashlib
    sha = hashlib.sha256(Path(out_path).read_bytes()).hexdigest()
    Path(str(out_path) + ".sha256").write_text(sha + "  " + Path(out_path).name + "\n", encoding="utf-8")
    tab = Counter((it["type_de_question"], it["split"]) for it in items)
    print(len(items), "items | DEV", sum(1 for i in items if i["split"] == "DEV"), "TEST", sum(1 for i in items if i["split"] == "TEST"), "| problèmes :", bad)
    for t in order:
        print(f"  {t:16} DEV {tab[(t, 'DEV')]:3}  TEST {tab[(t, 'TEST')]:3}")
    print("sha256", sha)
    return bad


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "benchmark_v1_draft.jsonl"
    sys.exit(1 if finalize(out) else 0)
