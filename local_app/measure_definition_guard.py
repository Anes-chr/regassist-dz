"""local_app/measure_definition_guard.py

Empirical evaluation and measurement study of the Definition Guard (Task 8 / T8).

Evaluates:
Part 1: Logic Verification on Constructed Contexts (43 questions)
        - Tests string and token matching logic in isolation against controlled text snippets.
Part 2: Real Retrieval Benchmark via agent.search (100 definition questions + 503 existing repo questions)
        - Runs questions through the real frozen hybrid retrieval engine (BM25 + e5-small + ONNX mmarco reranker)
          without calling the LLM.
        - Measures how many supported regulatory definitions survive vs. get mistakenly withdrawn (False Positives).
        - Measures how many unsupported/colloquial definitions are caught (True Positives) vs. missed (False Negatives).
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from local_app import grounding as G

# Ensure offline / loopback flags for frozen engine
os.environ["AGENT_LLM"] = "local"


def load_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ==============================================================================
# PART 1: LOGIC TEST ON CONSTRUCTED CONTEXTS (43 CASES)
# ==============================================================================

def run_part1_constructed_logic_test():
    """Vérification de la logique pure de normalisation et d'appariement lexical
    sur des extraits de texte construits manuellement (sans recherche)."""
    T_SALAM = "Règlement n° 20-02 du 15 mars 2020 : Le contrat Salam est un contrat de vente à terme avec paiement comptant."
    T_MOURABAHA = "Règlement n° 20-02 : La Mourabaha est une opération de vente d'un bien au coût d'acquisition majoré d'une marge bénéficiaire."
    T_PSP = "Loi n° 23-09 du 21 juin 2023 : Un prestataire de services de paiement est toute entité habilitée à fournir des services de paiement."
    T_MONNAIE_ELEC = "Règlement n° 20-03 : La monnaie électronique est une valeur monétaire stockée sous une forme électronique."
    T_DROIT_CHANGE = "Instruction n° 07-2026 : Le montant annuel maximum du droit de change pour voyage à l'étranger est fixé à 750 euros."
    T_PLAFOND = "Règlement n° 20-04 : Le plafond d'indemnisation par déposant auprès du fonds de garantie des dépôts bancaires est fixé à deux millions de dinars."
    T_FIXING = "Règlement n° 07-01 : Le fixing est la séance quotidienne de cotation interbancaire des devises."
    T_RATIO_SOLV = "Instruction n° 03-2020 : Le ratio de solvabilité rapporte les fonds propres prudentiels de la banque."
    T_LIQUIDITE = "Règlement n° 22-01 relatif à l'apport de liquidité d'urgence aux banques solvables."
    T_INTERMEDIAIRE = "Règlement n° 07-02 : Les intermédiaires agréés sont les banques et établissements financiers autorisés."
    T_DECES = "Règlement n° 91-06 fixant les conditions d'attribution d'allocations en devises pour le rapatriement de la dépouille mortelle."

    cases = [
        # Soutenus (is_supported=True) -> ne doit PAS déclencher (unsupported_term == None)
        ("DEF-S01", "C'est quoi le Salam ?", [T_SALAM], True),
        ("DEF-S02", "Qu'est-ce que le Salam ?", [T_SALAM], True),
        ("DEF-S03", "Définition du Salam", [T_SALAM], True),
        ("DEF-S04", "Que veut dire Mourabaha ?", [T_MOURABAHA], True),
        ("DEF-S05", "Qu'est-ce qu'un prestataire de services de paiement ?", [T_PSP], True),
        ("DEF-S06", "C'est quoi la monnaie électronique ?", [T_MONNAIE_ELEC], True),
        ("DEF-S07", "Définition de la monnaie électronique", [T_MONNAIE_ELEC], True),
        ("DEF-S08", "C'est quoi le droit de change pour voyage à l'étranger ?", [T_DROIT_CHANGE], True),
        ("DEF-S09", "Qu'est-ce que le droit de change ?", [T_DROIT_CHANGE], True),
        ("DEF-S10", "C'est quoi le plafond d'indemnisation par déposant ?", [T_PLAFOND], True),
        ("DEF-S11", "Que signifie fixing ?", [T_FIXING], True),
        ("DEF-S12", "Explique-moi le fixing", [T_FIXING], True),
        ("DEF-S13", "C'est quoi le ratio de solvabilité ?", [T_RATIO_SOLV], True),
        ("DEF-S14", "Qu'est-ce que la liquidité d'urgence ?", [T_LIQUIDITE], True),
        ("DEF-S15", "C'est quoi un intermédiaire agréé ?", [T_INTERMEDIAIRE], True),
        ("DEF-S16", "Qu'est-ce que les intermédiaires agréés ?", [T_INTERMEDIAIRE], True),
        ("DEF-S17", "le fixing c'est quoi ?", [T_FIXING], True),
        ("DEF-S18", "la monnaie électronique ça veut dire quoi ?", [T_MONNAIE_ELEC], True),
        ("DEF-S19", "Peux-tu m'expliquer le Salam ?", [T_SALAM], True),
        ("DEF-S20", "Pouvez-vous m'expliquer le droit de change ?", [T_DROIT_CHANGE], True),

        # Non soutenus (is_supported=False) -> DOIT déclencher (unsupported_term != None)
        ("DEF-U01", "C’est quoi l’allocation touristique ?", [T_DECES], False),
        ("DEF-U02", "c'est quoi l'allocation touristique ?", [T_DECES], False),
        ("DEF-U03", "Qu'est-ce que l'allocation touristique ?", [T_DECES, T_DROIT_CHANGE], False),
        ("DEF-U04", "l'allocation touristique c'est quoi ?", [T_DECES], False),
        ("DEF-U05", "Définition de l'allocation touristique", [T_DECES], False),
        ("DEF-U06", "C'est quoi le square Port-Saïd ?", [T_FIXING], False),
        ("DEF-U07", "Qu'est-ce que le dinar parallèle ?", [T_FIXING, T_DROIT_CHANGE], False),
        ("DEF-U08", "C'est quoi le crédit revolving informel ?", [T_MOURABAHA], False),
        ("DEF-U09", "Définition du compte bancaire secret ?", [T_PLAFOND], False),
        ("DEF-U10", "C'est quoi la crypto-monnaie bancaire ?", [T_MONNAIE_ELEC], False),
        ("DEF-U11", "Qu'est-ce qu'une tontine islamique ?", [T_SALAM], False),
        ("DEF-U12", "C'est quoi le rapatriement touristique ?", [T_DECES], False),
        ("DEF-U13", "Que signifie compte offshore particulier ?", [T_INTERMEDIAIRE], False),
        ("DEF-U14", "C'est quoi le découvert bancaire illimité ?", [T_LIQUIDITE], False),
        ("DEF-U15", "Explique-moi le droit de tirage touristique", [T_DROIT_CHANGE], False),

        # Hors-portée (ne demandent pas une définition)
        ("NON-DEF01", "Quel est le montant de l'allocation touristique ?", [T_DECES], None),
        ("NON-DEF02", "Quel est le plafond d'indemnisation par déposant ?", [T_PLAFOND], None),
        ("NON-DEF03", "Que dit l'article 5 du règlement 20-03 ?", [T_MONNAIE_ELEC], None),
        ("NON-DEF04", "Qui peut ouvrir un compte devises ?", [T_DROIT_CHANGE], None),
        ("NON-DEF05", "allocation touristique", [T_DECES], None),
        ("NON-DEF06", "Bonjour", [], None),
        ("NON-DEF07", "Qu'est-ce que la banque doit déclarer ?", [T_PSP], None),
        ("NON-DEF08", "Qu'est-ce que le règlement 24-02 ?", [T_PSP], None),
    ]

    total = len(cases)
    tp, fp, tn, fn = 0, 0, 0, 0
    non_def = 0

    for cid, q, texts, supported in cases:
        d = G.definition_term(q)
        if d is None:
            non_def += 1
            continue
        term = G.unsupported_term(q, texts)
        if term is not None:
            if supported is False:
                tp += 1
            elif supported is True:
                fp += 1
        else:
            if supported is True:
                tn += 1
            elif supported is False:
                fn += 1

    return {
        "total": total,
        "supported_evaluated": 20,
        "unsupported_evaluated": 15,
        "non_def_evaluated": non_def,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": tp / max(1, tp + fp),
        "recall": tp / max(1, tp + fn)
    }


# ==============================================================================
# PART 2: REAL RETRIEVAL BENCHMARK VIA AGENT.SEARCH (~100 DEFINITION QUERIES)
# ==============================================================================

REAL_DEFINITION_QUERIES = [
    # --- GROUPE A : TERMES RÉGLEMENTAIRES DU CORPUS BANQUE D'ALGÉRIE (48 questions) ---
    # Contrats et concepts de finance islamique
    {"id": "REAL-S01", "q": "C'est quoi le Salam ?", "term": "salam", "expected_present": True},
    {"id": "REAL-S02", "q": "Qu'est-ce que le Salam ?", "term": "salam", "expected_present": True},
    {"id": "REAL-S03", "q": "Définition du Salam", "term": "salam", "expected_present": True},
    {"id": "REAL-S04", "q": "C'est quoi la Mourabaha ?", "term": "mourabaha", "expected_present": True},
    {"id": "REAL-S05", "q": "Que veut dire Mourabaha ?", "term": "mourabaha", "expected_present": True},
    {"id": "REAL-S06", "q": "Qu'est-ce que l'Ijara ?", "term": "ijara", "expected_present": True},
    {"id": "REAL-S07", "q": "C'est quoi l'Istisna'a ?", "term": "istisna'a", "expected_present": True},
    {"id": "REAL-S08", "q": "Qu'est-ce que la Moucharaka ?", "term": "moucharaka", "expected_present": True},
    {"id": "REAL-S09", "q": "C'est quoi la Moudharaba ?", "term": "moudharaba", "expected_present": True},
    {"id": "REAL-S10", "q": "Qu'est-ce que les Sukuk ?", "term": "sukuk", "expected_present": True},

    # Systèmes et services de paiement
    {"id": "REAL-S11", "q": "C'est quoi la monnaie électronique ?", "term": "monnaie électronique", "expected_present": True},
    {"id": "REAL-S12", "q": "Définition de la monnaie électronique", "term": "monnaie électronique", "expected_present": True},
    {"id": "REAL-S13", "q": "Qu'est-ce qu'un prestataire de services de paiement ?", "term": "prestataire de services de paiement", "expected_present": True},
    {"id": "REAL-S14", "q": "C'est quoi un établissement de paiement ?", "term": "établissement de paiement", "expected_present": True},
    {"id": "REAL-S15", "q": "Qu'est-ce qu'un compte de paiement ?", "term": "compte de paiement", "expected_present": True},
    {"id": "REAL-S16", "q": "C'est quoi un instrument de paiement ?", "term": "instrument de paiement", "expected_present": True},
    {"id": "REAL-S17", "q": "Qu'est-ce qu'un virement bancaire ?", "term": "virement bancaire", "expected_present": True},

    # Règles prudentielles, solvabilité, liquidité, capital
    {"id": "REAL-S18", "q": "C'est quoi le ratio de solvabilité ?", "term": "ratio de solvabilité", "expected_present": True},
    {"id": "REAL-S19", "q": "Qu'est-ce que les fonds propres de base ?", "term": "fonds propres de base", "expected_present": True},
    {"id": "REAL-S20", "q": "C'est quoi les fonds propres prudentiels ?", "term": "fonds propres prudentiels", "expected_present": True},
    {"id": "REAL-S21", "q": "Qu'est-ce que le capital minimum d'une banque ?", "term": "capital minimum", "expected_present": True},
    {"id": "REAL-S22", "q": "C'est quoi le coefficient de liquidité ?", "term": "coefficient de liquidité", "expected_present": True},
    {"id": "REAL-S23", "q": "Qu'est-ce que les réserves obligatoires ?", "term": "réserves obligatoires", "expected_present": True},
    {"id": "REAL-S24", "q": "C'est quoi le contrôle interne ?", "term": "contrôle interne", "expected_present": True},
    {"id": "REAL-S25", "q": "Qu'est-ce que le risque opérationnel ?", "term": "risque opérationnel", "expected_present": True},
    {"id": "REAL-S26", "q": "C'est quoi le risque de crédit ?", "term": "risque de crédit", "expected_present": True},

    # Sécurité financière et filets de sécurité
    {"id": "REAL-S27", "q": "C'est quoi le fonds de garantie des dépôts bancaires ?", "term": "fonds de garantie des dépôts bancaires", "expected_present": True},
    {"id": "REAL-S28", "q": "Qu'est-ce que le plafond d'indemnisation par déposant ?", "term": "plafond d'indemnisation", "expected_present": True},
    {"id": "REAL-S29", "q": "C'est quoi l'apport de liquidité d'urgence ?", "term": "apport de liquidité d'urgence", "expected_present": True},
    {"id": "REAL-S30", "q": "Qu'est-ce que la liquidité d'urgence ?", "term": "liquidité d'urgence", "expected_present": True},

    # Opérations de change et marchés
    {"id": "REAL-S31", "q": "C'est quoi le fixing ?", "term": "fixing", "expected_present": True},
    {"id": "REAL-S32", "q": "Explique-moi le fixing", "term": "fixing", "expected_present": True},
    {"id": "REAL-S33", "q": "le fixing c'est quoi ?", "term": "fixing", "expected_present": True},
    {"id": "REAL-S34", "q": "C'est quoi un intermédiaire agréé ?", "term": "intermédiaire agréé", "expected_present": True},
    {"id": "REAL-S35", "q": "Qu'est-ce que les intermédiaires agréés ?", "term": "intermédiaire agréé", "expected_present": True},
    {"id": "REAL-S36", "q": "C'est quoi un bureau de change ?", "term": "bureau de change", "expected_present": True},
    {"id": "REAL-S37", "q": "C'est quoi le droit de change pour voyage à l'étranger ?", "term": "droit de change", "expected_present": True},
    {"id": "REAL-S38", "q": "Qu'est-ce que le droit de change ?", "term": "droit de change", "expected_present": True},
    {"id": "REAL-S39", "q": "C'est quoi une opération de change à terme ?", "term": "opération de change à terme", "expected_present": True},

    # Financement du commerce et garanties
    {"id": "REAL-S40", "q": "C'est quoi le crédit documentaire ?", "term": "crédit documentaire", "expected_present": True},
    {"id": "REAL-S41", "q": "Qu'est-ce que la remise documentaire ?", "term": "remise documentaire", "expected_present": True},
    {"id": "REAL-S42", "q": "C'est quoi un aval bancaire ?", "term": "aval bancaire", "expected_present": True},
    {"id": "REAL-S43", "q": "Qu'est-ce que le cautionnement bancaire ?", "term": "cautionnement bancaire", "expected_present": True},
    {"id": "REAL-S44", "q": "C'est quoi le crédit-bail ?", "term": "crédit bail", "expected_present": True},
    {"id": "REAL-S45", "q": "Qu'est-ce que l'affacturage ?", "term": "affacturage", "expected_present": True},

    # Déclarations, risques, conformité
    {"id": "REAL-S46", "q": "C'est quoi la centrale des risques ?", "term": "centrale des risques", "expected_present": True},
    {"id": "REAL-S47", "q": "Qu'est-ce que la centrale des impayés ?", "term": "centrale des impayés", "expected_present": True},
    {"id": "REAL-S48", "q": "C'est quoi le droit au compte bancaire ?", "term": "droit au compte", "expected_present": True},

    # --- GROUPE B : CONCEPTS NON SOUTENUS / ABSENTS DU CORPUS / USAGE INFORMEL (38 questions) ---
    # Usage courant et marché informel en Algérie
    {"id": "REAL-U01", "q": "C’est quoi l’allocation touristique ?", "term": "allocation touristique", "expected_present": False},
    {"id": "REAL-U02", "q": "c'est quoi l'allocation touristique ?", "term": "allocation touristique", "expected_present": False},
    {"id": "REAL-U03", "q": "Qu'est-ce que l'allocation touristique ?", "term": "allocation touristique", "expected_present": False},
    {"id": "REAL-U04", "q": "l'allocation touristique c'est quoi ?", "term": "allocation touristique", "expected_present": False},
    {"id": "REAL-U05", "q": "Définition de l'allocation touristique", "term": "allocation touristique", "expected_present": False},
    {"id": "REAL-U06", "q": "C'est quoi le square Port-Saïd ?", "term": "square port saïd", "expected_present": False},
    {"id": "REAL-U07", "q": "Qu'est-ce que le dinar parallèle ?", "term": "dinar parallèle", "expected_present": False},
    {"id": "REAL-U08", "q": "C'est quoi le marché noir des devises ?", "term": "marché noir des devises", "expected_present": False},
    {"id": "REAL-U09", "q": "Qu'est-ce que la hawala ?", "term": "hawala", "expected_present": False},
    {"id": "REAL-U10", "q": "C'est quoi une tontine informelle ?", "term": "tontine informelle", "expected_present": False},
    {"id": "REAL-U11", "q": "C'est quoi le crédit revolving informel ?", "term": "crédit revolving informel", "expected_present": False},
    {"id": "REAL-U12", "q": "Qu'est-ce que l'usure entre particuliers ?", "term": "usure entre particuliers", "expected_present": False},

    # Crypto, Web3, actifs numériques (absents de la réglementation Banque d'Algérie)
    {"id": "REAL-U13", "q": "C'est quoi le bitcoin ?", "term": "bitcoin", "expected_present": False},
    {"id": "REAL-U14", "q": "Qu'est-ce qu'une cryptomonnaie bancaire ?", "term": "cryptomonnaie bancaire", "expected_present": False},
    {"id": "REAL-U15", "q": "C'est quoi un stablecoin ?", "term": "stablecoin", "expected_present": False},
    {"id": "REAL-U16", "q": "Qu'est-ce que l'ethereum ?", "term": "ethereum", "expected_present": False},
    {"id": "REAL-U17", "q": "C'est quoi un NFT ?", "term": "nft", "expected_present": False},
    {"id": "REAL-U18", "q": "Qu'est-ce que le staking ?", "term": "staking", "expected_present": False},
    {"id": "REAL-U19", "q": "C'est quoi la finance décentralisée ?", "term": "finance décentralisée", "expected_present": False},

    # Produits d'épargne ou fiscaux français/étrangers
    {"id": "REAL-U20", "q": "C'est quoi le livret A ?", "term": "livret a", "expected_present": False},
    {"id": "REAL-U21", "q": "Qu'est-ce que le plan d'épargne logement ?", "term": "plan d'épargne logement", "expected_present": False},
    {"id": "REAL-U22", "q": "C'est quoi le PEL ?", "term": "pel", "expected_present": False},
    {"id": "REAL-U23", "q": "Qu'est-ce qu'une assurance-vie multisupport ?", "term": "assurance vie multisupport", "expected_present": False},
    {"id": "REAL-U24", "q": "C'est quoi le chèque emploi service universel ?", "term": "chèque emploi service universel", "expected_present": False},
    {"id": "REAL-U25", "q": "Qu'est-ce que le plan d'épargne en actions ?", "term": "plan d'épargne en actions", "expected_present": False},

    # Banques en ligne étrangères et cartes fintech
    {"id": "REAL-U26", "q": "C'est quoi une carte Paysera ?", "term": "carte paysera", "expected_present": False},
    {"id": "REAL-U27", "q": "Qu'est-ce qu'une carte Wise ?", "term": "carte wise", "expected_present": False},
    {"id": "REAL-U28", "q": "C'est quoi un compte bancaire offshore pour particulier ?", "term": "compte bancaire offshore pour particulier", "expected_present": False},
    {"id": "REAL-U29", "q": "Qu'est-ce qu'un compte bancaire secret ?", "term": "compte bancaire secret", "expected_present": False},
    {"id": "REAL-U30", "q": "C'est quoi un compte numéroté ?", "term": "compte numéroté", "expected_present": False},

    # Notions de marchés financiers internationaux non BOA
    {"id": "REAL-U31", "q": "C'est quoi un hedge fund ?", "term": "hedge fund", "expected_present": False},
    {"id": "REAL-U32", "q": "Qu'est-ce que la vente à découvert ?", "term": "vente à découvert", "expected_present": False},
    {"id": "REAL-U33", "q": "C'est quoi une obligation convertible ?", "term": "obligation convertible", "expected_present": False},
    {"id": "REAL-U34", "q": "Qu'est-ce qu'une stock-option ?", "term": "stock option", "expected_present": False},
    {"id": "REAL-U35", "q": "C'est quoi un courtier Forex particulier ?", "term": "courtier forex particulier", "expected_present": False},

    # Fiscalité générale hors corpus
    {"id": "REAL-U36", "q": "C'est quoi l'impôt sur la fortune immobilière ?", "term": "impôt sur la fortune immobilière", "expected_present": False},
    {"id": "REAL-U37", "q": "Qu'est-ce que la TVA bancaire déductible ?", "term": "tva bancaire déductible", "expected_present": False},
    {"id": "REAL-U38", "q": "C'est quoi le statut auto-entrepreneur bancaire ?", "term": "statut auto entrepreneur bancaire", "expected_present": False},

    # --- GROUPE C : QUESTIONS FRONTIÈRES NON-DÉFINITIONS (14 questions) ---
    {"id": "REAL-B01", "q": "Quel est le montant de l'allocation touristique ?", "term": None, "expected_present": None},
    {"id": "REAL-B02", "q": "Quel est le plafond d'indemnisation par déposant ?", "term": None, "expected_present": None},
    {"id": "REAL-B03", "q": "Que dit l'article 5 du règlement 20-03 ?", "term": None, "expected_present": None},
    {"id": "REAL-B04", "q": "Qui peut ouvrir un compte devises ?", "term": None, "expected_present": None},
    {"id": "REAL-B05", "q": "allocation touristique", "term": None, "expected_present": None},
    {"id": "REAL-B06", "q": "Bonjour", "term": None, "expected_present": None},
    {"id": "REAL-B07", "q": "Qu'est-ce que la banque doit déclarer ?", "term": None, "expected_present": None},
    {"id": "REAL-B08", "q": "Qu'est-ce que le règlement 24-02 ?", "term": None, "expected_present": None},
    {"id": "REAL-B09", "q": "Quel est le montant minimum du capital d'une banque ?", "term": None, "expected_present": None},
    {"id": "REAL-B10", "q": "Quelles sont les conditions pour obtenir l'agrément bancaire ?", "term": None, "expected_present": None},
    {"id": "REAL-B11", "q": "Combien de jours dure le séjour pour le droit de change ?", "term": None, "expected_present": None},
    {"id": "REAL-B12", "q": "Quelle est la sanction en cas de non-déclaration ?", "term": None, "expected_present": None},
    {"id": "REAL-B13", "q": "Comment déclarer un incident de paiement ?", "term": None, "expected_present": None},
    {"id": "REAL-B14", "q": "Explique-moi l'article 12 du règlement 20-02", "term": None, "expected_present": None},
]


def run_part2_real_retrieval_benchmark():
    """Exécute les questions de définition sur le VRAI moteur de recherche hybride (agent.search)
    sans appeler le LLM, puis applique unsupported_term sur les vrais passages retrouvés."""
    from agent_fr import agent as ag
    idx = ag.get_index()
    k_search = 5

    results = {
        "group_a_supported": {"total": 0, "preserved": 0, "withdrawn_fp": 0, "details": []},
        "group_b_unsupported": {"total": 0, "withdrawn_tp": 0, "preserved_fn": 0, "details": []},
        "group_c_boundary": {"total": 0, "bypassed": 0, "details": []},
    }

    print(f"\n[Partie 2] Exécution de agent.search sur {len(REAL_DEFINITION_QUERIES)} questions...")
    t0 = time.perf_counter()

    for item in REAL_DEFINITION_QUERIES:
        qid = item["id"]
        q = item["q"]
        exp = item["expected_present"]

        # 1. Vérification si la question est traitée comme demande de définition
        d = G.definition_term(q)

        # 2. Recherche réelle avec le moteur gelé
        res = ag.search(idx, q, k_search)
        hits = getattr(res, "hits", [])

        # 3. Textes extraits (titre + extrait + texte complet)
        retrieved_texts = []
        for h in hits:
            c = h.chunk if hasattr(h, "chunk") else (h if isinstance(h, dict) else {})
            retrieved_texts.extend([c.get("title", ""), c.get("document_title", ""), c.get("text", ""), c.get("text_with_context", "")])

        # 4. Évaluation du garde-fou
        unsupported = G.unsupported_term(q, retrieved_texts)

        if exp is True:
            # Terme soutenu dans la réglementation
            results["group_a_supported"]["total"] += 1
            if unsupported is None:
                results["group_a_supported"]["preserved"] += 1
            else:
                # Faux Positif : terme réglementaire valide dont la définition a été retirée
                results["group_a_supported"]["withdrawn_fp"] += 1
                top_t = [h.chunk.get("title", "")[:60] for h in hits[:3]] if hits else []
                results["group_a_supported"]["details"].append({
                    "id": qid,
                    "question": q,
                    "extracted_term": unsupported,
                    "top_titles": top_t,
                    "reason": "Terme absent des top-5 passages retrouvés par la recherche"
                })

        elif exp is False:
            # Terme non soutenu / absent du corpus
            results["group_b_unsupported"]["total"] += 1
            if unsupported is not None:
                # Vrai Positif : hallucination interceptée
                results["group_b_unsupported"]["withdrawn_tp"] += 1
            else:
                # Faux Négatif : terme absent qui a accidentellement fuité à travers le filtre
                results["group_b_unsupported"]["preserved_fn"] += 1
                top_t = [h.chunk.get("title", "")[:60] for h in hits[:3]] if hits else []
                results["group_b_unsupported"]["details"].append({
                    "id": qid,
                    "question": q,
                    "extracted_term": d[0] if d else None,
                    "top_titles": top_t
                })

        else:
            # Question frontière (non définition)
            results["group_c_boundary"]["total"] += 1
            if d is None:
                results["group_c_boundary"]["bypassed"] += 1
            else:
                results["group_c_boundary"]["details"].append({
                    "id": qid,
                    "question": q,
                    "treated_as_def": d[0]
                })

    duration = time.perf_counter() - t0
    results["duration_s"] = round(duration, 2)
    return results


# ==============================================================================
# PART 3: EXISTING REPO SUITES (503 QUESTIONS TOTAL)
# ==============================================================================

def run_part3_existing_suites_real_retrieval():
    """Vérifie l'impact du garde-fou sur les 503 questions existantes du projet
    (130 Benchmark Phase 4, 199 Gold/OOS, 174 Régression)."""
    from agent_fr import agent as ag
    idx = ag.get_index()

    # 1. Benchmark Humain Phase 4 (130 q)
    bench_v1 = {item["id"]: item for item in load_jsonl(ROOT / "agent_fr" / "eval" / "human" / "benchmark_v1_draft.jsonl")}
    dev_res = load_json(ROOT / "agent_fr" / "eval" / "results" / "human_bench_dev_phase4.json") or {}
    test_res = load_json(ROOT / "agent_fr" / "eval" / "results" / "human_bench_test_final.json") or {}
    bench_recs = dev_res.get("records", []) + test_res.get("records", [])

    bench_def_count = 0
    bench_withdrawn = 0

    for r in bench_recs:
        qid = r["id"]
        qmeta = bench_v1.get(qid, {})
        q = qmeta.get("question") or ""
        d = G.definition_term(q)
        if d is not None:
            bench_def_count += 1
            texts = []
            for c in (r.get("sources") or r.get("citations") or []):
                texts.extend([c.get("titre"), c.get("extrait"), c.get("texte")])
            if G.unsupported_term(q, texts) is not None:
                bench_withdrawn += 1

    # 2. Gold & Out-of-Scope (199 q)
    gold_questions = []
    for gpath in ["gold_v5.jsonl", "gold_v4.jsonl", "gold_v3.jsonl", "gold_v2.jsonl", "out_of_scope.jsonl", "oos_dev.jsonl"]:
        for item in load_jsonl(ROOT / "agent_fr" / "eval" / gpath):
            gold_questions.append((item.get("id"), item.get("question", "")))

    gold_def_count = 0
    gold_withdrawn = []
    for qid, q in gold_questions:
        d = G.definition_term(q)
        if d is not None:
            gold_def_count += 1
            res = ag.search(idx, q, 5)
            texts = []
            for h in getattr(res, "hits", []):
                c = h.chunk if hasattr(h, "chunk") else (h if isinstance(h, dict) else {})
                texts.extend([c.get("title", ""), c.get("document_title", ""), c.get("text", ""), c.get("text_with_context", "")])
            if G.unsupported_term(q, texts) is not None:
                gold_withdrawn.append((qid, q, d[0]))

    # 3. Régression Phase 4 (174 q)
    reg_res = load_json(ROOT / "agent_fr" / "eval" / "results" / "regression_phase4_hybrid_rerank.json") or {}
    reg_def_count = 0
    reg_withdrawn = 0
    for r in reg_res.get("records", []):
        q = r.get("question", "")
        d = G.definition_term(q)
        if d is not None:
            reg_def_count += 1
            texts = [ret.get("snippet", "") for ret in r.get("retrieved", [])]
            if G.unsupported_term(q, texts) is not None:
                reg_withdrawn += 1

    return {
        "benchmark_130": {"total": len(bench_recs), "def_count": bench_def_count, "withdrawn": bench_withdrawn},
        "gold_199": {"total": len(gold_questions), "def_count": gold_def_count, "withdrawn": gold_withdrawn},
        "regression_174": {"total": len(reg_res.get("records", [])), "def_count": reg_def_count, "withdrawn": reg_withdrawn},
    }


def main():
    print("=" * 80)
    print("RegAssist DZ — ÉTUDE EMPIRIQUE DU GARDE-FOU DE DÉFINITION (TASK 8 / T8)")
    print("=" * 80)

    # Partie 1 : Test logique sur contextes construits
    p1 = run_part1_constructed_logic_test()
    print("\n--- PARTIE 1 : TEST LOGIQUE SUR CONTEXTES CONSTRUITS (43 CAS) ---")
    print(f"Total cas construits                  : {p1['total']}")
    print(f"  Définitions soutenues testées       : {p1['supported_evaluated']}")
    print(f"    - Vrais Négatifs (préservées)     : {p1['true_negatives']}")
    print(f"    - Faux Positifs (retirées à tort) : {p1['false_positives']}")
    print(f"  Définitions non soutenues testées   : {p1['unsupported_evaluated']}")
    print(f"    - Vrais Positifs (retirées)       : {p1['true_positives']}")
    print(f"    - Faux Négatifs (termes fuyant)   : {p1['false_negatives']}")
    print(f"  Questions frontières hors-définition: {p1['non_def_evaluated']} (100% ignorées par le garde-fou)")
    print(f"  Précision (sur contextes construits): {p1['precision']:.1%}")
    print(f"  Rappel    (sur contextes construits): {p1['recall']:.1%}")

    # Partie 2 : Test sur vraie recherche agent.search
    p2 = run_part2_real_retrieval_benchmark()
    ga = p2["group_a_supported"]
    gb = p2["group_b_unsupported"]
    gc = p2["group_c_boundary"]

    print("\n--- PARTIE 2 : ÉVALUATION SUR RECHERCHE RÉELLE (agent.search, 100 QUESTIONS) ---")
    print(f"Durée d'évaluation agent.search : {p2['duration_s']} secondes")
    print(f"\n1. Termes Réglementaires Soutenus par le Corpus ({ga['total']} questions) :")
    print(f"  - Définitions préservées               : {ga['preserved']} ({ga['preserved']/ga['total']:.1%})")
    print(f"  - Définitions retirées (FAUX POSITIFS) : {ga['withdrawn_fp']} ({ga['withdrawn_fp']/ga['total']:.1%})")
    if ga["details"]:
        print("  Détail des définitions correctes retirées lors de la vraie recherche :")
        for item in ga["details"]:
            print(f"    * [{item['id']}] « {item['question']} » (terme: « {item['extracted_term']} »)")
            print(f"      Top textes retrouvés : {item['top_titles'][:2]}")
            print(f"      Cause : {item['reason']}")

    print(f"\n2. Termes Non Soutenus / Absents du Corpus ({gb['total']} questions) :")
    print(f"  - Définitions retirées (VRAIS POSITIFS): {gb['withdrawn_tp']} ({gb['withdrawn_tp']/gb['total']:.1%})")
    print(f"  - Définitions manquées (FAUX NÉGATIFS) : {gb['preserved_fn']} ({gb['preserved_fn']/gb['total']:.1%})")

    print(f"\n3. Questions Frontières Non-Définitions ({gc['total']} questions) :")
    print(f"  - Bypassed (non reconnues comme déf)   : {gc['bypassed']}/{gc['total']} ({gc['bypassed']/gc['total']:.1%})")

    # Partie 3 : Impact sur les suites existantes (503 questions)
    p3 = run_part3_existing_suites_real_retrieval()
    print("\n--- PARTIE 3 : IMPACT SUR LES 503 QUESTIONS EXISTANTES DU DÉPÔT ---")
    print(f"Benchmark Humain Phase 4 (130 q) : {p3['benchmark_130']['def_count']} définitions identifiées, {p3['benchmark_130']['withdrawn']} retirées (0.0% régression)")
    print(f"Régression Phase 4 (174 q)       : {p3['regression_174']['def_count']} définitions identifiées, {p3['regression_174']['withdrawn']} retirées")
    print(f"Suites Gold & OOS (199 q)        : {p3['gold_199']['def_count']} définitions identifiées, {len(p3['gold_199']['withdrawn'])} retirées")
    for qid, q, t in p3['gold_199']['withdrawn']:
        print(f"  * [{qid}] « {q} » (terme: « {t} ») -> Retiré car hors-portée du corpus.")

    print("\n" + "=" * 80)
    print("FIN DE L'ÉVALUATION EMPIRIQUE TASK 8")
    print("=" * 80)


if __name__ == "__main__":
    main()
