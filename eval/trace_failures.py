"""Trace failed or gate-dropped eval questions step-by-step."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from db.session import async_session_maker
from retrieval.confidence_gate import ConfidenceGate
from retrieval.hybrid_search import HybridSearcher
from retrieval.query_normalizer import query_normalizer
from retrieval.reranker import CrossEncoderReranker


async def trace_queries():
    with open("eval/eval_set.json", "r", encoding="utf-8") as f:
        items = json.load(f)

    target_ids = {
        "eval_12",
        "eval_18",
        "eval_24",
        "eval_25",
        "eval_28",
        "eval_31",
        "eval_32",
        "eval_34",
        "eval_35",
    }
    trace_items = [it for it in items if it["id"] in target_ids]

    searcher = HybridSearcher()
    reranker = CrossEncoderReranker()
    gate = ConfidenceGate()

    async with async_session_maker() as session:
        for it in trace_items:
            q = it["query"]
            exp_docs = {UUID(u) for u in it["expected_document_ids"]}
            print(f"==================================================")
            print(f"TRACE: [{it['id']}] {q}")
            print(f"==================================================")
            norm = query_normalizer.normalize(q)
            print(f"  Query Normalizer vector expansion  : {norm.expanded_vector}")
            print(f"  Query Normalizer keyword expansion : {norm.expanded_keyword}")
            print(f"  Detected Departments               : {norm.detected_departments}")

            # 1. Vector Search Candidates
            v_res = await searcher.vector_searcher.search(session, norm.expanded_vector or q, top_k=20)
            v_rank = next((r for r, c in enumerate(v_res, 1) if c.document_id in exp_docs), None)
            v_top_sim = v_res[0].vector_score if v_res else 0.0

            # 2. Keyword Search Candidates
            k_res = await searcher.keyword_searcher.search(session, norm.expanded_keyword or q, top_k=20)
            k_rank = next((r for r, c in enumerate(k_res, 1) if c.document_id in exp_docs), None)

            # 3. Hybrid RRF Search
            rrf_res = await searcher.search(session, q, top_k=20)
            rrf_rank = next((r for r, c in enumerate(rrf_res, 1) if c.document_id in exp_docs), None)

            print(f"  Vector Search      : Rank {v_rank or 'NOT FOUND'} (top vector sim: {v_top_sim:.4f})")
            print(f"  Keyword (FTS)      : Rank {k_rank or 'NOT FOUND'} (total FTS hits: {len(k_res)})")
            print(f"  Hybrid (RRF Fusion): Rank {rrf_rank or 'NOT FOUND'} (in candidate pool of {len(rrf_res)})")

            # 4. Reranking (Using current baseline expanded_vector)
            rerank_q = norm.expanded_vector or q
            reranked = await reranker.arerank(rerank_q, rrf_res, top_k=10)
            rerank_rank = next((r for r, c in enumerate(reranked, 1) if c.document_id in exp_docs), None)
            top_score = reranked[0].rerank_score if reranked else 0.0

            # 5. Also test reranking with NATURAL query to see immediate comparison
            reranked_natural = await reranker.arerank(q, rrf_res, top_k=10)
            natural_rank = next((r for r, c in enumerate(reranked_natural, 1) if c.document_id in exp_docs), None)
            natural_top_score = reranked_natural[0].rerank_score if reranked_natural else 0.0

            gate_res = gate.evaluate(reranked)

            exp_score = reranked[rerank_rank - 1].rerank_score if rerank_rank else None
            natural_exp_score = reranked_natural[natural_rank - 1].rerank_score if natural_rank else None

            print(f"  Baseline Reranked  : Rank {rerank_rank or 'NOT FOUND'} (Expected Chunk Score: {exp_score})")
            print(f"  Baseline Gate Top  : {top_score:.4f} -> Gate Passed: {gate_res.passed}")
            print(f"  [Natural Q Rerank] : Rank {natural_rank or 'NOT FOUND'} (Score: {natural_exp_score}, Top: {natural_top_score:.4f})")
            print()


if __name__ == "__main__":
    asyncio.run(trace_queries())

