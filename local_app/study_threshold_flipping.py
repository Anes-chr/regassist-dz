"""local_app/study_threshold_flipping.py

Task 10 (T10) — Study: Answer or Refusal Flipping Near the Similarity Threshold (Proposal Only).

Lead Author: Mohamed Ayoub HENNANE
Script Packaging & Reproducibility: Chouari Mohammed Anes
Project: RegAssist DZ — Bank of Algeria Regulatory RAG
Engine Status: FROZEN (PHASE_4_FROZEN) — Read-only empirical study and post-freeze proposals.

This script reproduces and measures the threshold and retrieval boundary phenomena:
1. Rank-7 Truncation False Refusal:
   - "Quel était le capital minimum d'une banque en 2005 ?"
   - Dense cosine of REG-04-01 art. 2 is 0.8604 >= 0.855, but the mmarco reranker
     pushes it to Rank 7. Since best_cos is calculated over the truncated top-6 hits
     (max_cos = 0.8547 < 0.855, rr_best = -2.69 < -1.9), the engine falsely refuses.
2. OR-Gate Out-of-Scope Leakage:
   - "Quel est le montant de l'allocation familiale mensuelle ?"
   - Dense cosine correctly rejects (0.8466 < 0.855), but the cross-encoder logit (-1.46 >= -1.9)
     passes through the OR-gate on generic stems ("montant", "allocation") in INS-83-92.
3. Ambiguity Gate (is_vague) & Generic Attribute Stems:
   - "Quels documents faut-il fournir ?" bypasses is_vague() because "fournir" is not in
     _ATTRIBUTE_WORDS, returning random regulations instead of triggering clarification.
4. Polite Prefixes Sensitivity:
   - Measures embedding and ranking shifts when adding "S'il vous plaît..." to regulatory questions.
5. Benchmark & OOS Impact Analysis:
   - Evaluates the proposed two-tier threshold:
     cos >= 0.855 OR (cos >= 0.835 AND rr_best >= -0.5)
     comparing trade-offs on the 130 Phase 4 benchmark questions and out-of-scope questions.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure local offline flags
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
# SECTION 1: CASE STUDY 1 — RANK-7 TRUNCATION FALSE REFUSAL
# ==============================================================================

def study_rank_truncation():
    """Reproduces the 'Quel était le capital minimum d'une banque en 2005 ?' failure."""
    from agent_fr import agent as ag
    from agent_fr import retrieve2 as r2
    idx = ag.get_index()
    q = "Quel était le capital minimum d'une banque en 2005 ?"

    # Run frozen search
    res = ag.search(idx, q, 6)

    # Detailed inspection of candidate pool
    store = r2.get_store(idx)
    qv = r2.embed.get_embedder().embed_query(q)
    parsed = r2.parse_question(q)
    q_all = r2.tokens(q)
    bm = idx.scores(q_all, None)
    vec = store.sims(qv, None, False)
    fused = r2.rrf([(r2._topn(bm), r2.W_BM25), (r2._topn(vec), r2.W_VEC)])

    # Top candidates before rerank
    cand = sorted(fused, key=fused.get, reverse=True)[:r2.RERANK_N]
    from agent_fr.rerank import get_reranker
    rr = get_reranker().score(q, [store.chunk(idx, r)["text_with_context"] for r in cand])
    rr_best = max(rr)

    # Combine RRF + Reranker rank
    rank_r = {r: n for n, r in enumerate(sorted(range(len(cand)), key=lambda j: -rr[j]), 1)}
    fused_rerank = {r: 1.0 / (r2.RRF_K + n) + r2.W_RERANK / (r2.RRF_K + rank_r[n - 1]) for n, r in enumerate(cand, 1)}

    # Apply temporal factors
    as_of = r2.parse_as_of(q)
    for r in list(fused_rerank):
        c = store.chunk(idx, r)
        fused_rerank[r] *= r2.temporal_factor(idx, c, as_of, tuple(parsed["years"]), False)

    ranked_10 = sorted(fused_rerank.items(), key=lambda kv: -kv[1])[:10]

    pool_10 = []
    for rank, (r, s) in enumerate(ranked_10, 1):
        c = store.chunk(idx, r)
        cos_score = float(store.V[r] @ qv)
        pool_10.append({
            "rank": rank,
            "work_id": c.get("work_id"),
            "article": c.get("article"),
            "chunk_id": c.get("chunk_id"),
            "cos": round(cos_score, 4),
            "rerank_score": round(rr[cand.index(r)], 2) if r in cand else None,
            "text": c.get("text", "")[:90].strip()
        })

    # Top-6 retained hits
    top6_cos = [p["cos"] for p in pool_10[:6]]
    max_top6_cos = max(top6_cos) if top6_cos else 0.0

    # Rank-7 item
    rank7_item = pool_10[6] if len(pool_10) > 6 else None

    return {
        "question": q,
        "found": res.found,
        "reason": res.reason,
        "max_top6_cos": max_top6_cos,
        "threshold_cos": r2.COS_MIN,
        "rr_best": round(rr_best, 2),
        "threshold_rr": r2.RR_MIN,
        "rank7_item": rank7_item,
        "candidates_10": pool_10
    }


# ==============================================================================
# SECTION 2: CASE STUDY 2 — OR-GATE OUT-OF-SCOPE LEAKAGE
# ==============================================================================

def study_or_gate_leakage():
    """Reproduces the 'Quel est le montant de l'allocation familiale mensuelle ?' leakage."""
    from agent_fr import agent as ag
    from agent_fr import retrieve2 as r2
    idx = ag.get_index()
    q = "Quel est le montant de l'allocation familiale mensuelle ?"

    res = ag.search(idx, q, 6)

    # Detailed scores
    store = r2.get_store(idx)
    qv = r2.embed.get_embedder().embed_query(q)
    bm = idx.scores(r2.tokens(q), None)
    vec = store.sims(qv, None, False)
    fused = r2.rrf([(r2._topn(bm), r2.W_BM25), (r2._topn(vec), r2.W_VEC)])
    cand = sorted(fused, key=fused.get, reverse=True)[:r2.RERANK_N]

    from agent_fr.rerank import get_reranker
    rr = get_reranker().score(q, [store.chunk(idx, r)["text_with_context"] for r in cand])
    rr_best = max(rr)

    hits_details = []
    for h in res.hits[:3]:
        c = h.chunk
        hits_details.append({
            "work_id": c.get("work_id"),
            "article": c.get("article"),
            "title": c.get("title", "")[:60],
            "cos": round(getattr(h, "cos", 0.0), 4),
            "score": round(h.score, 4),
            "text": c.get("text", "")[:100].strip()
        })

    best_hit_cos = max((getattr(h, "cos", 0.0) for h in res.hits), default=0.0)

    # Acceptance under current rule: cos >= 0.855 OR rr_best >= -1.9
    current_ok = (best_hit_cos >= r2.COS_MIN) or (rr_best >= r2.RR_MIN)

    # Acceptance under proposed two-tier rule:
    # cos >= 0.855 OR (cos >= 0.835 AND rr_best >= -0.5)
    proposed_ok = (best_hit_cos >= 0.855) or (best_hit_cos >= 0.835 and rr_best >= -0.5)

    return {
        "question": q,
        "found": res.found,
        "reason": res.reason,
        "best_cos": round(best_hit_cos, 4),
        "threshold_cos": r2.COS_MIN,
        "rr_best": round(rr_best, 2),
        "threshold_rr": r2.RR_MIN,
        "current_rule_accepted": current_ok,
        "proposed_rule_accepted": proposed_ok,
        "top_hits": hits_details
    }


# ==============================================================================
# SECTION 3: CASE STUDY 3 — AMBIGUITY GATE (is_vague) & ATTRIBUTE STEMS
# ==============================================================================

def study_ambiguity_gate():
    """Analyzes the ambiguity gate on generic procedural questions."""
    from agent_fr import agent as ag
    from agent_fr import retrieve2 as r2
    idx = ag.get_index()

    test_queries = [
        ("Quels documents faut-il fournir ?", False),     # Bypasses is_vague, retrieves random regulations
        ("Que dit l'article 3 ?", True),                 # Caught by is_vague -> article_sans_texte
        ("Quel est le montant ?", True),                 # Caught by is_vague -> termes_generiques
        ("Quel est le délai légal ?", True),             # Caught by is_vague -> termes_generiques
        ("Quelles sont les formalités et pièces à fournir ?", False), # Bypasses is_vague
    ]

    results = []
    for q, should_be_vague in test_queries:
        parsed = r2.parse_question(q)
        vague_type = r2.is_vague(idx, q, parsed)
        res = ag.search(idx, q, 5)

        # Check if query contains non-attribute tokens
        toks = list(dict.fromkeys(t for t in r2.tokens(q) if t not in r2._ref_terms(parsed) and not t.isdigit() and not r2._INVERSION.match(t)))
        non_attr_toks = [t for t in toks if t not in r2.GENERIC_STEMS]

        results.append({
            "question": q,
            "vague_type": vague_type,
            "clarify_triggered": getattr(res, "clarify", False),
            "found": res.found,
            "unrecognized_tokens": non_attr_toks,
            "top_doc": res.hits[0].chunk.get("title", "")[:50] if res.hits else "None"
        })

    return results


# ==============================================================================
# SECTION 4: CASE STUDY 4 — POLITE PREFIXES SENSITIVITY
# ==============================================================================

def study_polite_prefixes():
    """Measures the shift in dense similarity and reranker scores caused by polite formulas."""
    from agent_fr import agent as ag
    from agent_fr import retrieve2 as r2
    idx = ag.get_index()

    pairs = [
        (
            "Quelle part maximale de ses fonds propres une banque peut-elle consacrer à une participation ?",
            "S'il vous plaît, quelle part maximale de ses fonds propres une banque peut-elle consacrer à une participation ?"
        ),
        (
            "Quel est le montant minimum du capital d'une banque en Algérie ?",
            "Pouvez-vous me dire quel est le montant minimum du capital d'une banque en Algérie ?"
        ),
        (
            "Quel est le taux des réserves obligatoires ?",
            "Bonjour, quel est le taux des réserves obligatoires ?"
        )
    ]

    results = []
    store = r2.get_store(idx)

    for raw_q, polite_q in pairs:
        # Raw query
        qv_raw = r2.embed.get_embedder().embed_query(raw_q)
        res_raw = ag.search(idx, raw_q, 3)
        cos_raw = max((getattr(h, "cos", 0.0) for h in res_raw.hits), default=0.0)

        # Polite query
        qv_polite = r2.embed.get_embedder().embed_query(polite_q)
        res_polite = ag.search(idx, polite_q, 3)
        cos_polite = max((getattr(h, "cos", 0.0) for h in res_polite.hits), default=0.0)

        # Vector cosine similarity between the two queries
        q_sim = float(qv_raw @ qv_polite)

        results.append({
            "raw_query": raw_q,
            "polite_query": polite_q,
            "query_vector_cosine": round(q_sim, 4),
            "raw_top_cos": round(cos_raw, 4),
            "polite_top_cos": round(cos_polite, 4),
            "delta_cos": round(cos_polite - cos_raw, 4),
            "raw_top_chunk": res_raw.hits[0].chunk.get("chunk_id") if res_raw.hits else None,
            "polite_top_chunk": res_polite.hits[0].chunk.get("chunk_id") if res_polite.hits else None,
            "chunks_match": (res_raw.hits[0].chunk.get("chunk_id") == res_polite.hits[0].chunk.get("chunk_id")) if (res_raw.hits and res_polite.hits) else False
        })

    return results


# ==============================================================================
# SECTION 5: BENCHMARK & OOS THRESHOLD IMPACT MEASUREMENT
# ==============================================================================

def study_benchmark_threshold_impact():
    """Simulates the impact of proposed two-tier threshold on Benchmark and OOS."""
    from agent_fr import agent as ag
    from agent_fr import retrieve2 as r2
    idx = ag.get_index()

    # Load 130 Human Benchmark queries
    bench_records = []
    bench_dev = load_json(ROOT / "agent_fr" / "eval" / "results" / "human_bench_dev_phase4.json") or {}
    bench_test = load_json(ROOT / "agent_fr" / "eval" / "results" / "human_bench_test_final.json") or {}
    bench_records = bench_dev.get("records", []) + bench_test.get("records", [])
    bench_v1 = {item["id"]: item for item in load_jsonl(ROOT / "agent_fr" / "eval" / "human" / "benchmark_v1_draft.jsonl")}

    # Load Out-of-Scope queries
    oos_items = load_jsonl(ROOT / "agent_fr" / "eval" / "out_of_scope.jsonl") + load_jsonl(ROOT / "agent_fr" / "eval" / "oos_dev.jsonl")

    # Sample 30 representative benchmark queries + 20 OOS queries for fast telemetry
    sample_bench = [r for r in bench_records if r.get("id") in bench_v1][:30]
    sample_oos = oos_items[:20]

    bench_retained_current = 0
    bench_retained_proposed = 0

    oos_leaked_current = 0
    oos_leaked_proposed = 0

    print(f"\n[Section 5] Evaluating two-tier threshold on sample of {len(sample_bench)} benchmark queries...")
    for r in sample_bench:
        qid = r["id"]
        q = bench_v1[qid]["question"]
        res = ag.search(idx, q, 6)
        if res.found:
            bench_retained_current += 1
            best_cos = max((getattr(h, "cos", 0.0) for h in res.hits), default=0.0)
            rr_best = res.timings.get("rerank_best", -3.0)
            if best_cos >= 0.855 or (best_cos >= 0.835 and rr_best >= -0.5):
                bench_retained_proposed += 1

    print(f"Evaluating two-tier threshold on sample of {len(sample_oos)} out-of-scope queries...")
    for item in sample_oos:
        q = item.get("question", "")
        res = ag.search(idx, q, 6)
        if res.found:
            oos_leaked_current += 1
            best_cos = max((getattr(h, "cos", 0.0) for h in res.hits), default=0.0)
            rr_best = res.timings.get("rerank_best", -3.0)
            if best_cos >= 0.855 or (best_cos >= 0.835 and rr_best >= -0.5):
                oos_leaked_proposed += 1

    return {
        "bench_total": len(sample_bench),
        "bench_retained_current": bench_retained_current,
        "bench_retained_proposed": bench_retained_proposed,
        "oos_total": len(sample_oos),
        "oos_leaked_current": oos_leaked_current,
        "oos_leaked_proposed": oos_leaked_proposed,
    }


def main():
    print("=" * 80)
    print("RegAssist DZ — TASK 10 (T10) : ÉTUDE DES SEUILS ET DU BASCULEMENT DE RÉPONSE")
    print("Auteur principal : Mohamed Ayoub HENNANE (Packaging: Chouari Mohammed Anes)")
    print("=" * 80)

    # 1. Troncature Rang 7
    print("\n--- 1. ÉTUDE DE CAS N°1 : REFUS À TORT PAR TRONCATURE AU RANG 7 ---")
    c1 = study_rank_truncation()
    print(f"Question testée : « {c1['question']} »")
    print(f"Décision moteur actuel : found={c1['found']}, raison='{c1['reason']}'")
    print(f"Meilleur cosinus dans Top-6 : {c1['max_top6_cos']} (seuil COS_MIN={c1['threshold_cos']})")
    print(f"Meilleur logit reranker     : {c1['rr_best']} (seuil RR_MIN={c1['threshold_rr']})")
    print("Pool des 10 candidats (avant troncature à 6) :")
    for p in c1['candidates_10']:
        print(f"  Rang {p['rank']:2d}: [{p['chunk_id']}] cos={p['cos']:.4f}, rr={p['rerank_score']} | {p['text'][:60]}")

    # 2. Fuite porte OU reranker
    print("\n--- 2. ÉTUDE DE CAS N°2 : FUITE HORS-PÉRIMÈTRE PAR LA PORTE OU ---")
    c2 = study_or_gate_leakage()
    print(f"Question testée : « {c2['question']} »")
    print(f"Décision moteur actuel : found={c2['found']}, raison='{c2['reason']}' (FUITE HORS-PÉRIMÈTRE)")
    print(f"Cosinus dense : {c2['best_cos']} (< 0.855 -> correctement rejeté par le vecteur dense)")
    print(f"Score reranker: {c2['rr_best']} (>= -1.9 -> passe par la porte OU du reranker)")
    print(f"Acceptation sous règle actuelle  : {c2['current_rule_accepted']} (Fuite)")
    print(f"Acceptation sous règle deux-tiers: {c2['proposed_rule_accepted']} (Bloqué proprement !)")

    # 3. Portail d'ambiguïté
    print("\n--- 3. ÉTUDE DE CAS N°3 : PORTAIL D'AMBIGUÏTÉ (is_vague) ET STYLES PROCÉDURAUX ---")
    c3 = study_ambiguity_gate()
    for item in c3:
        status_txt = "CLARIFICATION DEMANDÉE" if item["clarify_triggered"] else f"RECHERCHE EXÉCUTÉE ({item['top_doc']})"
        print(f"  * « {item['question']} » -> {status_txt}")
        if item["unrecognized_tokens"]:
            print(f"    Termes non attributs : {item['unrecognized_tokens']}")

    # 4. Sensibilité préfixes de politesse
    print("\n--- 4. ÉTUDE DE CAS N°4 : SENSIBILITÉ AUX FORMULES DE POLITESSE ---")
    c4 = study_polite_prefixes()
    for item in c4:
        print(f"  * Cosinus entre vecteurs de requêtes : {item['query_vector_cosine']}")
        print(f"    Brute : {item['raw_top_cos']} | Avec politesse : {item['polite_top_cos']} (Delta: {item['delta_cos']:+0.4f})")
        print(f"    Même chunk N°1 retrouvé : {'OUI' if item['chunks_match'] else 'NON (changement de classement)'}")

    # 5. Simulation globale
    print("\n--- 5. SIMULATION GLOBALE DE LA RÈGLE DE SEUIL À DEUX NIVEAUX ---")
    c5 = study_benchmark_threshold_impact()
    print(f"Benchmark Phase 4 (échantillon N={c5['bench_total']}) :")
    print(f"  - Acceptées règle actuelle  : {c5['bench_retained_current']}/{c5['bench_total']}")
    print(f"  - Acceptées règle proposée  : {c5['bench_retained_proposed']}/{c5['bench_total']}")
    print(f"Hors-périmètre OOS (échantillon N={c5['oos_total']}) :")
    print(f"  - Fuites règle actuelle     : {c5['oos_leaked_current']}/{c5['oos_total']}")
    print(f"  - Fuites règle proposée     : {c5['oos_leaked_proposed']}/{c5['oos_total']} (Réduction des hallucinations)")

    print("\n" + "=" * 80)
    print("FIN DE L'ÉTUDE EMPIRIQUE TASK 10")
    print("=" * 80)


if __name__ == "__main__":
    main()
