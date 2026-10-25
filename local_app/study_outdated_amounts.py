"""local_app/study_outdated_amounts.py

Task 9 (T9) — Study: Outdated Amounts When an Article Was Amended (Proposal Only).

This script performs an empirical investigation across the frozen Bank of Algeria
regulatory corpus (PHASE_4_FROZEN) to quantify:
1. The prevalence of amended and repealed articles in the corpus containing numerical amounts
   (amounts in DA, percentages, reserve rates, capital requirements, guarantee ceilings, ratios).
2. The frequency with which outdated/superseded amounts co-occur with or outrank currently
   applicable amounts in the Top-K retrieval results of the frozen hybrid engine (agent.search).
3. The root causes of temporal inversions in retrieval (e.g. lexical BM25 matching historical titles,
   embedding insensitivity to dates, terse amendment chunks lacking full contextual definitions).
4. Concrete evaluations of known critical cases (such as H129 deposit reserve rates, minimum bank
   capital across Reg. 04-01 / 08-04 / 18-03, deposit guarantee ceiling across Reg. 97-04 / 20-04,
   and travel foreign currency allowances).

NOTE: Read-only study. Preserves the frozen engine (agent_fr/ is untouched).
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Set offline flags for frozen engine
os.environ["AGENT_LLM"] = "local"


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


AMOUNT_REGEX = re.compile(
    r"(?:\b\d+(?:[\s.,]\d+)*\s*(?:dinars?|DA|milliards?|millions?|euros?|€|dollars?|\$|%|pour\s*cent))\b",
    re.IGNORECASE
)


# ==============================================================================
# SECTION 1: CORPUS-WIDE SCAN OF AMENDED ARTICLES & NUMERICAL VALUES
# ==============================================================================

def scan_corpus_amendments():
    """Scans corpus/metadata/legal_status.json and chunks_fr.jsonl to catalog:
    - Total documents and chunks
    - Replaced/modified/abrogated documents and articles
    - Frequency of numerical figures/amounts in amended vs active chunks
    """
    legal_path = ROOT / "corpus" / "metadata" / "legal_status.json"
    chunks_path = ROOT / "corpus" / "chunks" / "chunks_fr.jsonl"
    docs_path = ROOT / "corpus" / "metadata" / "documents_fr.json"

    legal = load_json(legal_path) or {}
    docs = load_json(docs_path) or []
    chunks = load_jsonl(chunks_path)

    doc_status = legal.get("documents", {})
    art_status = legal.get("articles", {})
    rules = legal.get("regles", {})

    stats = {
        "total_documents": len(docs),
        "total_chunks": len(chunks),
        "doc_status_counts": defaultdict(int),
        "art_status_counts": defaultdict(int),
        "art_rules_counts": defaultdict(int),
        "amended_articles_total": len(art_status),
        "chunks_with_amounts_total": 0,
        "superseded_chunks_with_amounts": 0,
        "active_chunks_with_amounts": 0,
        "sample_amended_articles_with_amounts": []
    }

    for d in docs:
        st = doc_status.get(d.get("work_id", ""), {}).get("statut", "UNKNOWN")
        stats["doc_status_counts"][st] += 1

    for art_key, st_info in art_status.items():
        st = st_info.get("statut", "UNKNOWN")
        rule = st_info.get("regle", "")
        stats["art_status_counts"][st] += 1
        stats["art_rules_counts"][rule] += 1

    for c in chunks:
        text = c.get("text", "")
        matches = AMOUNT_REGEX.findall(text)
        has_amount = bool(matches)
        if has_amount:
            stats["chunks_with_amounts_total"] += 1

        chunk_id = c.get("chunk_id", "")
        work_id = c.get("work_id", "")
        art = str(c.get("article") or "")

        # Check document-level and article-level status
        doc_st = doc_status.get(work_id, {}).get("statut", "UNKNOWN")
        art_key = f"{work_id}::{art}" if art else None
        art_st_info = art_status.get(art_key, {})
        art_st = art_st_info.get("statut", doc_st)

        is_superseded = art_st in ("ABROGATED", "REPLACED", "MODIFIED", "HISTORICAL")

        if is_superseded and has_amount:
            stats["superseded_chunks_with_amounts"] += 1
            if len(stats["sample_amended_articles_with_amounts"]) < 10:
                stats["sample_amended_articles_with_amounts"].append({
                    "chunk_id": chunk_id,
                    "work_id": work_id,
                    "article": art,
                    "statut": art_st,
                    "regle": art_st_info.get("regle", "DOC_STATUS"),
                    "amounts": matches[:3],
                    "excerpt": text[:120].strip()
                })
        elif not is_superseded and has_amount:
            stats["active_chunks_with_amounts"] += 1

    return stats


# ==============================================================================
# SECTION 2: EMPIRICAL RETRIEVAL EXPERIMENTS ON OUTDATED AMOUNTS (agent.search)
# ==============================================================================

REPRESENTATIVE_AMOUNT_QUERIES = [
    {
        "id": "CASE-01-CAPITAL-BANQUE",
        "topic": "Capital minimum des banques",
        "question": "Quel est le montant minimum du capital d'une banque en Algérie ?",
        "current_norm": "Règlement n° 2024-02 du 6 février 2024 (REG-24-02)",
        "current_amount": "20 milliards de DA (banques ordinaires et d'affaires), 10 milliards de DA (banques digitales)",
        "current_chunk": "REG-24-02.fr::article-2 (art. 2, p. 2)",
        "historical_norms": [
            {"ref": "Règlement n° 18-03", "amount": "20 milliards de DA", "status": "ABROGATED (par REG-24-02)", "chunk": "REG-18-03.fr~2::article-2 (art. 2, p. 1)"},
            {"ref": "Règlement n° 08-04", "amount": "10 milliards de DA", "status": "ABROGATED (par REG-18-03)", "chunk": "REG-08-04.fr~2::article-2 (art. 2, p. 1)"},
            {"ref": "Règlement n° 04-01", "amount": "2,5 milliards de DA", "status": "ABROGATED (par REG-08-04)", "chunk": "REG-04-01.fr~2::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "REG-24-02"
    },
    {
        "id": "CASE-02-CAPITAL-ETAB-FIN",
        "topic": "Capital minimum des établissements financiers",
        "question": "Quel est le capital minimum exigé pour un établissement financier ?",
        "current_norm": "Règlement n° 2024-02 du 6 février 2024 (REG-24-02)",
        "current_amount": "6,5 milliards de DA",
        "current_chunk": "REG-24-02.fr::article-2 (art. 2, p. 2)",
        "historical_norms": [
            {"ref": "Règlement n° 18-03", "amount": "6,5 milliards de DA", "status": "ABROGATED (par REG-24-02)", "chunk": "REG-18-03.fr~2::article-2 (art. 2, p. 1)"},
            {"ref": "Règlement n° 08-04", "amount": "3,5 milliards de DA", "status": "ABROGATED (par REG-18-03)", "chunk": "REG-08-04.fr~2::article-2 (art. 2, p. 1)"},
            {"ref": "Règlement n° 04-01", "amount": "500 millions de DA", "status": "ABROGATED (par REG-08-04)", "chunk": "REG-04-01.fr~2::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "REG-24-02"
    },
    {
        "id": "CASE-03-PLAFOND-GARANTIE",
        "topic": "Plafond d'indemnisation du fonds de garantie des dépôts (FGDB)",
        "question": "Quel est le plafond d'indemnisation par déposant garanti par la Banque d'Algérie ?",
        "current_norm": "Règlement n° 2020-03 du 15 mars 2020 (REG-20-03)",
        "current_amount": "2 000 000 DA (deux millions de dinars)",
        "current_chunk": "REG-20-03.fr::article-10 (art. 10, p. 3)",
        "historical_norms": [
            {"ref": "Règlement n° 97-04", "amount": "600 000 DA (six cents mille dinars)", "status": "REPLACED (par REG-04-03 puis REG-20-03)", "chunk": "REG-97-04.fr::article-9 (art. 9, p. 3)"}
        ],
        "expected_active_work_id": "REG-20-03"
    },
    {
        "id": "CASE-04-RESERVES-OBLIG-H129",
        "topic": "Taux des réserves obligatoires (Cas critique H129)",
        "question": "Quel est le taux actuel des réserves obligatoires ?",
        "current_norm": "Instruction n° 01-2026 (1 %)",
        "current_amount": "1 %",
        "current_chunk": "INS-01-26.fr::article-2 (art. 2, p. 1)",
        "historical_norms": [
            {"ref": "Instruction n° 02-2023", "amount": "3 %", "status": "REPLACED (par INS-09-25 puis INS-01-26)", "chunk": "INS-02-23.fr::article-2 (art. 2, p. 1)"},
            {"ref": "Instruction n° 02-2004", "amount": "6,5 %", "status": "REPLACED", "chunk": "INS-02-04.fr::article-3 (art. 3, p. 1)"}
        ],
        "expected_active_work_id": "INS-01-26"
    },
    {
        "id": "CASE-05-DROIT-CHANGE-VOYAGE",
        "topic": "Droit de change pour voyage à l'étranger",
        "question": "Quel est le montant annuel du droit de change pour voyage à l'étranger ?",
        "current_norm": "Instruction n° 07-2026 (750 euros par an, 300 euros pour les mineurs)",
        "current_amount": "750 euros",
        "current_chunk": "INS-07-26.fr::article-2 (art. 2, p. 1)",
        "historical_norms": [
            {"ref": "Instruction n° 08-97", "amount": "15 000 DA", "status": "ABROGATED (par INS-05-2025 puis INS-07-2026)", "chunk": "INS-08-97.fr::article-2 (art. 2, p. 1)"},
            {"ref": "Instruction n° 05-2025", "amount": "750 euros", "status": "ABROGATED (par INS-07-2026)", "chunk": "INS-05-25.fr::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "INS-07-26"
    },
    {
        "id": "CASE-06-RATIO-SOLVABILITE",
        "topic": "Ratio de solvabilité prudentiel global",
        "question": "Quel est le ratio de solvabilité minimum exigé des banques ?",
        "current_norm": "Règlement n° 14-01 / Instruction n° 03-2020 (9,5 % et 7 % Tier 1)",
        "current_amount": "9,5 % (globaux) / 7 % (base)",
        "current_chunk": "REG-14-01.fr::article-2 (art. 2, p. 1)",
        "historical_norms": [
            {"ref": "Règlement n° 91-09", "amount": "8 % (ratio Cooke)", "status": "ABROGATED (par REG-14-01)", "chunk": "REG-91-09.fr::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "REG-14-01"
    },
    {
        "id": "CASE-07-COEFF-LIQUIDITE",
        "topic": "Coefficient minimum de liquidité",
        "question": "Quel est le pourcentage minimum du coefficient de liquidité d'une banque ?",
        "current_norm": "Règlement n° 11-04 (100 %)",
        "current_amount": "100 %",
        "current_chunk": "REG-11-04.fr::article-3 (art. 3, p. 2)",
        "historical_norms": [
            {"ref": "Règlement n° 91-11", "amount": "60 %", "status": "ABROGATED (par REG-11-04)", "chunk": "REG-91-11.fr::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "REG-11-04"
    },
    {
        "id": "CASE-08-DIVISION-RISQUES",
        "topic": "Plafond des grands risques par bénéficiaire",
        "question": "Quel est le plafond maximum des engagements sur un même bénéficiaire par rapport aux fonds propres ?",
        "current_norm": "Règlement n° 14-02 (25 %)",
        "current_amount": "25 %",
        "current_chunk": "REG-14-02.fr::article-4 (art. 4, p. 2)",
        "historical_norms": [
            {"ref": "Règlement n° 91-08", "amount": "25 % (base calcul modifiée)", "status": "ABROGATED (par REG-14-02)", "chunk": "REG-91-08.fr::article-2 (art. 2, p. 1)"}
        ],
        "expected_active_work_id": "REG-14-02"
    }
]


def run_retrieval_investigation():
    """Runs agent.search for each representative query and measures:
    - Co-occurrence: does an outdated passage appear in Top-5 alongside the active passage?
    - Ranking inversion: does an outdated passage outrank the active passage?
    - Amount collision: does an outdated amount appear in the Top-1 chunk?
    """
    from agent_fr import agent as ag
    from agent_fr import answer as ans
    idx = ag.get_index()

    case_results = []
    co_occurrence_count = 0
    inversion_count = 0
    outdated_top1_count = 0

    print(f"\n[Section 2] Running retrieval on {len(REPRESENTATIVE_AMOUNT_QUERIES)} amended amount test cases...")

    for case in REPRESENTATIVE_AMOUNT_QUERIES:
        cid = case["id"]
        q = case["question"]
        exp_work = case["expected_active_work_id"]

        res = ag.search(idx, q, k=6)
        hits = getattr(res, "hits", [])

        hit_details = []
        active_rank = None
        outdated_ranks = []
        found_active = False
        found_outdated = False

        for rank, h in enumerate(hits, start=1):
            c = h.chunk if hasattr(h, "chunk") else (h if isinstance(h, dict) else {})
            work_id = c.get("work_id", "")
            title = c.get("title", "")
            text = c.get("text", "")
            matches = AMOUNT_REGEX.findall(text)

            # Determine legal status via answer.statut_juridique
            st_info = ans.statut_juridique(idx, c)
            st = st_info.get("statut", "UNKNOWN")

            is_active = (work_id == exp_work) or (st == "ACTIVE")
            is_outdated = st in ("ABROGATED", "REPLACED", "MODIFIED", "HISTORICAL")

            if work_id == exp_work and active_rank is None:
                active_rank = rank
                found_active = True

            if is_outdated:
                outdated_ranks.append(rank)
                found_outdated = True

            hit_details.append({
                "rank": rank,
                "work_id": work_id,
                "title": title[:70],
                "article": c.get("article"),
                "statut": st,
                "amounts_found": matches[:3],
                "score": round(getattr(h, "score", 0.0), 3)
            })

        # Check conditions
        co_occur = found_active and found_outdated
        inversion = (outdated_ranks and (active_rank is None or outdated_ranks[0] < active_rank))
        top1_outdated = bool(outdated_ranks and outdated_ranks[0] == 1)

        if co_occur:
            co_occurrence_count += 1
        if inversion:
            inversion_count += 1
        if top1_outdated:
            outdated_top1_count += 1

        case_results.append({
            "id": cid,
            "topic": case["topic"],
            "question": q,
            "expected_active": exp_work,
            "active_rank": active_rank,
            "outdated_ranks": outdated_ranks,
            "co_occurrence": co_occur,
            "temporal_inversion": inversion,
            "top1_outdated": top1_outdated,
            "hits": hit_details
        })

    return {
        "total_cases": len(REPRESENTATIVE_AMOUNT_QUERIES),
        "co_occurrence_count": co_occurrence_count,
        "temporal_inversion_count": inversion_count,
        "top1_outdated_count": outdated_top1_count,
        "cases": case_results
    }


def main():
    print("=" * 80)
    print("RegAssist DZ — TASK 9 (T9) : ÉTUDE DES MONTANTS PÉRIMÉS (ARTICLES MODIFIÉS)")
    print("=" * 80)

    # 1. Analyse statique du corpus
    print("\n--- ÉTAPE 1 : CARTOGRAPHIE CORPUS-WIDE DES MODIFICATIONS ET MONTANTS ---")
    t0 = time.perf_counter()
    corpus_stats = scan_corpus_amendments()
    t_scan = round(time.perf_counter() - t0, 2)

    print(f"Total documents dans le corpus       : {corpus_stats['total_documents']}")
    print(f"Total chunks de texte               : {corpus_stats['total_chunks']}")
    print(f"Articles avec statut explicite       : {corpus_stats['amended_articles_total']}")
    print(f"  - Articles REPLACED (remplacés)   : {corpus_stats['art_status_counts']['REPLACED']}")
    print(f"  - Articles MODIFIED (modifiés)     : {corpus_stats['art_status_counts']['MODIFIED']}")
    print(f"  - Articles ABROGATED (abrogés)     : {corpus_stats['art_status_counts']['ABROGATED']}")
    print(f"  - Articles ACTIVE (en vigueur)     : {corpus_stats['art_status_counts']['ACTIVE']}")
    print(f"\nChunks contenant des montants chiffrés : {corpus_stats['chunks_with_amounts_total']}")
    print(f"  - Chunks de textes PÉRIMÉS avec montants : {corpus_stats['superseded_chunks_with_amounts']}")
    print(f"  - Chunks de textes ACTIFS avec montants  : {corpus_stats['active_chunks_with_amounts']}")

    # 2. Expérimentation empirique de recherche
    print("\n--- ÉTAPE 2 : MESURE EMPIRIQUE DE RECHERCHE HYBRIDE SUR LES MONTANTS ---")
    retrieval_res = run_retrieval_investigation()

    total_c = retrieval_res["total_cases"]
    co_occ = retrieval_res["co_occurrence_count"]
    inv = retrieval_res["temporal_inversion_count"]
    top1_out = retrieval_res["top1_outdated_count"]

    print(f"\nRésultats sur {total_c} requêtes types de montants réglementaires modifiés :")
    print(f"  - Co-occurrence périmé + actif dans Top-6 : {co_occ}/{total_c} ({co_occ/total_c:.1%})")
    print(f"  - Inversion temporelle (périmé > actif)   : {inv}/{total_c} ({inv/total_c:.1%})")
    print(f"  - Passage périmé classé N°1 (Top-1)       : {top1_out}/{total_c} ({top1_out/total_c:.1%})")

    print("\n--- ÉTAPE 3 : DÉTAIL DES CAS TYPES DE RECHERCHE ---")
    for c in retrieval_res["cases"]:
        print(f"\n[{c['id']}] {c['topic']}")
        print(f"  Question : « {c['question']} »")
        print(f"  Rang texte actif ({c['expected_active']}) : {c['active_rank'] or 'NON RETROUVÉ'}")
        print(f"  Rangs textes périmés : {c['outdated_ranks']}")
        print(f"  Inversion temporelle : {'OUI (Périmé devance l\'actif)' if c['temporal_inversion'] else 'NON'}")
        for h in c["hits"][:3]:
            print(f"    * Rang {h['rank']} [{h['statut']}] {h['work_id']} art. {h['article']} | Montants: {h['amounts_found']}")

    print("\n" + "=" * 80)
    print("FIN DE L'ÉTUDE EMPIRIQUE TASK 9")
    print("=" * 80)


if __name__ == "__main__":
    main()
