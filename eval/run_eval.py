"""Comprehensive RAG Retrieval and Grounding Evaluation Script for EduSync.

Evaluates:
- Recall@5, Recall@10
- Mean Reciprocal Rank (MRR)
- Confidence Gate Pass Rate
- False Abstention Rate (% of answerable queries where gate refused)
- Abstention Accuracy (on unanswerable queries)
- End-to-End Correctness with Citations
- Tune (2/3) vs Holdout (1/3) Split Comparison
- Pure Algorithmic Subset (Excluding data/eval edited queries eval_31, 32, 34, 35)
- Per-Stage Latency Breakdown (Normalization, Embedding, Vector SQL, Keyword SQL, RRF, Rerank, Gate, Total)
- Reranker Provider tracking (fails loudly on error, no silent fallbacks)
- Gemini {answerable, evidence} verification tracking
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from uuid import UUID

# Ensure backend package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from api.routes.chat import generate_llm_answer_async
from db.session import async_session_maker
from retrieval.confidence_gate import ConfidenceGate
from retrieval.hybrid_search import HybridSearcher
from retrieval.query_normalizer import query_normalizer
from retrieval.query_rewriter import query_rewriter
from retrieval.reranker import CrossEncoderReranker

# Silence verbose library logging during eval
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("eval")
logger.setLevel(logging.INFO)

DATA_EDITED_IDS = {"eval_31", "eval_32", "eval_34", "eval_35"}


def evaluate_split_metrics(items_data: list[dict], split_name: str = "ALL"):
    """Compute and format summary metrics for a given subset of evaluation items."""
    ans_items = [d for d in items_data if not d["is_unanswerable"]]
    unans_items = [d for d in items_data if d["is_unanswerable"]]

    n_ans = len(ans_items)
    n_unans = len(unans_items)
    n_total = len(items_data)

    hits_5 = sum(1 for d in ans_items if d["hit_5"])
    hits_10 = sum(1 for d in ans_items if d["hit_10"])
    gate_pass = sum(1 for d in ans_items if d["gate_passed"])
    false_abstentions = n_ans - gate_pass
    mrr_sum = sum(d["rr"] for d in ans_items)

    correct_abstentions = sum(1 for d in unans_items if d["gate_abstained"])
    e2e_correct_ans = sum(1 for d in ans_items if d.get("e2e_correct", False))
    e2e_correct_total = e2e_correct_ans + correct_abstentions

    recall_5 = (hits_5 / n_ans * 100) if n_ans else 0.0
    recall_10 = (hits_10 / n_ans * 100) if n_ans else 0.0
    mrr = (mrr_sum / n_ans) if n_ans else 0.0
    gate_pass_rate = (gate_pass / n_ans * 100) if n_ans else 0.0
    false_abstention_rate = (false_abstentions / n_ans * 100) if n_ans else 0.0
    abstention_acc = (correct_abstentions / n_unans * 100) if n_unans else 0.0
    e2e_acc = (e2e_correct_total / n_total * 100) if n_total else 0.0

    return {
        "split": split_name,
        "total": n_total,
        "n_ans": n_ans,
        "n_unans": n_unans,
        "recall_5": recall_5,
        "recall_10": recall_10,
        "mrr": mrr,
        "gate_pass_rate": gate_pass_rate,
        "false_abstention_rate": false_abstention_rate,
        "abstention_acc": abstention_acc,
        "e2e_acc": e2e_acc,
        "hits_5": hits_5,
        "hits_10": hits_10,
        "gate_pass": gate_pass,
        "false_abstentions": false_abstentions,
        "correct_abstentions": correct_abstentions,
        "e2e_correct_total": e2e_correct_total,
    }


async def run_evaluation(
    eval_set_path: Path,
    provider: str = "local",
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    rerank_mode: str = "natural",
    gate_threshold: float = 0.40,
    enable_gemini_check: bool = False,
):
    with open(eval_set_path, "r", encoding="utf-8") as f:
        eval_items = json.load(f)

    searcher = HybridSearcher()
    reranker = CrossEncoderReranker(provider=provider, model_name=model_name)
    gate = ConfidenceGate(threshold=gate_threshold)

    total_count = len(eval_items)

    latencies = {
        "rewrite": [],
        "norm": [],
        "embed": [],
        "search_vec_sql": [],
        "search_fts_sql": [],
        "search_rrf": [],
        "rerank": [],
        "gate": [],
        "gemini_check": [],
        "total": [],
    }

    eval_results = []

    print(f"\n{'='*75}")
    print(f"EduSync Retrieval Benchmark ({total_count} items)")
    print(f"Reranker Provider : {provider.upper()} (fails loudly on error)")
    print(f"Reranker Model    : {model_name}")
    print(f"Rerank Mode       : {rerank_mode.upper()}")
    print(f"Gate Threshold    : {gate_threshold:.2f}")
    print(f"Gemini Evidence   : {'ENABLED' if enable_gemini_check else 'DISABLED (Pure Gate)'}")
    print(f"{'='*75}\n")

    overall_start = time.time()

    async with async_session_maker() as session:
        for idx, item in enumerate(eval_items, 1):
            qid = item["id"]
            cat = item["category"]
            query = item["query"]
            split = item.get("split", "tune")
            is_unanswerable = item["is_unanswerable"]
            expected_doc_ids = {UUID(uid) for uid in item.get("expected_document_ids", [])}

            t0 = time.perf_counter()

            # 0. Conversational Query Rewriting (if conversation history present)
            search_query = query
            history = item.get("history")
            t_rewrite_ms = 0.0
            if history:
                t_rewrite_start = time.perf_counter()
                rewritten = await query_rewriter.rewrite(query=query, history=history)
                if rewritten.is_rewritten:
                    search_query = rewritten.standalone_query
                t_rewrite_ms = (time.perf_counter() - t_rewrite_start) * 1000
                latencies["rewrite"].append(t_rewrite_ms)

            # 1. Domain Query Normalization
            t_norm_start = time.perf_counter()
            norm = query_normalizer.normalize(search_query)
            t_norm_ms = (time.perf_counter() - t_norm_start) * 1000

            v_query = norm.expanded_vector or search_query
            k_query = norm.expanded_keyword or search_query
            target_depts = norm.detected_departments or None

            # 2a. Query Embedding Generation (dense vector)
            t_emb_start = time.perf_counter()
            query_embs = await searcher.embedder.aembed_texts([v_query], task="retrieval.query")
            query_emb = query_embs[0] if query_embs else None
            t_emb_ms = (time.perf_counter() - t_emb_start) * 1000

            # 2b. Vector Search (pgvector SQL execution)
            t_vec_start = time.perf_counter()
            vector_results = await searcher.vector_searcher.search(
                session=session,
                query=v_query,
                query_embedding=query_emb,
                top_k=40,
                departments=None,
            )
            t_vec_ms = (time.perf_counter() - t_vec_start) * 1000

            # 2c. Keyword Search (FTS SQL execution)
            t_fts_start = time.perf_counter()
            keyword_results = await searcher.keyword_searcher.search(
                session=session,
                query=k_query,
                top_k=40,
                departments=None,
            )
            t_fts_ms = (time.perf_counter() - t_fts_start) * 1000

            # 2d. Reciprocal Rank Fusion
            t_rrf_start = time.perf_counter()
            raw_chunks = searcher.reciprocal_rank_fusion(
                vector_results=vector_results,
                keyword_results=keyword_results,
                top_k=25,
                target_departments=target_depts,
            )
            t_rrf_ms = (time.perf_counter() - t_rrf_start) * 1000

            # 3. Cross-Encoder Reranking
            t_rerank_start = time.perf_counter()
            rerank_q = search_query if rerank_mode == "natural" else v_query
            reranked = await reranker.arerank(query=rerank_q, chunks=raw_chunks, top_k=10)
            t_rerank_ms = (time.perf_counter() - t_rerank_start) * 1000

            # 4. Confidence Gating
            t_gate_start = time.perf_counter()
            gate_res = gate.evaluate(reranked)
            t_gate_ms = (time.perf_counter() - t_gate_start) * 1000

            retrieved_doc_ids = [c.document_id for c in reranked]
            top_score = reranked[0].rerank_score if reranked else 0.0

            # 5. Production Gemini In-Prompt Evidence Verification Check
            t_gemini_ms = 0.0
            gemini_answerable = gate_res.passed
            if enable_gemini_check and gate_res.passed and reranked:
                t_gemini_start = time.perf_counter()
                context_excerpt = "\n".join([c.content[:2000] for c in reranked[:3]])
                try:
                    llm_check = await generate_llm_answer_async(search_query, context_excerpt)
                    gemini_answerable = bool(llm_check.answerable)
                except Exception as e:
                    logger.warning(f"Gemini evidence verification exception for '{search_query}': {e}")
                    gemini_answerable = gate_res.passed
                t_gemini_ms = (time.perf_counter() - t_gemini_start) * 1000

            total_q_ms = (time.perf_counter() - t0) * 1000

            latencies["norm"].append(t_norm_ms)
            latencies["embed"].append(t_emb_ms)
            latencies["search_vec_sql"].append(t_vec_ms)
            latencies["search_fts_sql"].append(t_fts_ms)
            latencies["search_rrf"].append(t_rrf_ms)
            latencies["rerank"].append(t_rerank_ms)
            latencies["gate"].append(t_gate_ms)
            if t_gemini_ms > 0:
                latencies["gemini_check"].append(t_gemini_ms)
            latencies["total"].append(total_q_ms)

            # Record Result
            res_dict = {
                "id": qid,
                "category": cat,
                "split": split,
                "query": query,
                "is_unanswerable": is_unanswerable,
                "top_score": top_score,
                "gate_passed": gate_res.passed if not enable_gemini_check else gemini_answerable,
                "gate_abstained": not gate_res.passed if not enable_gemini_check else not gemini_answerable,
                "hit_5": False,
                "hit_10": False,
                "rr": 0.0,
                "e2e_correct": False,
            }

            if is_unanswerable:
                res_dict["e2e_correct"] = res_dict["gate_abstained"]
                status_sym = "[OK: ABSTAINED]" if res_dict["gate_abstained"] else "[FAIL: FALSE POSITIVE]"
                print(f"[{idx:02d}/{total_count}] {status_sym} ({split:<7}) Q: {query[:40]:<40} | Score: {top_score:.3f}")
            else:
                top_5_docs = set(retrieved_doc_ids[:5])
                top_10_docs = set(retrieved_doc_ids[:10])

                hit_5 = bool(expected_doc_ids.intersection(top_5_docs))
                hit_10 = bool(expected_doc_ids.intersection(top_10_docs))
                res_dict["hit_5"] = hit_5
                res_dict["hit_10"] = hit_10

                rr = 0.0
                for rank, doc_id in enumerate(retrieved_doc_ids, 1):
                    if doc_id in expected_doc_ids:
                        rr = 1.0 / rank
                        break
                res_dict["rr"] = rr
                res_dict["e2e_correct"] = res_dict["gate_passed"] and hit_5

                hit_sym = "HIT@5" if hit_5 else ("HIT@10" if hit_10 else "MISS")
                gate_sym = "GATE_PASS" if res_dict["gate_passed"] else "GATE_FAIL"
                print(f"[{idx:02d}/{total_count}] [{hit_sym}|{gate_sym}] ({split:<7}) Q: {query[:38]:<38} | Top: {top_score:.3f} | RR: {rr:.2f}")

            eval_results.append(res_dict)
            await asyncio.sleep(0.01)

    total_wall_sec = time.time() - overall_start

    # Metrics computation
    n_all = len(eval_results)
    n_tune = sum(1 for d in eval_results if d["split"] == "tune")
    n_holdout = sum(1 for d in eval_results if d["split"] == "holdout")
    n_untouched = sum(1 for d in eval_results if d["id"] not in DATA_EDITED_IDS)

    m_all = evaluate_split_metrics(eval_results, f"ALL ({n_all})")
    m_tune = evaluate_split_metrics([d for d in eval_results if d["split"] == "tune"], f"TUNE ({n_tune})")
    m_holdout = evaluate_split_metrics([d for d in eval_results if d["split"] == "holdout"], f"HOLDOUT ({n_holdout})")
    m_untouched = evaluate_split_metrics([d for d in eval_results if d["id"] not in DATA_EDITED_IDS], f"UNTOUCHED ({n_untouched})")

    h_all = f"ALL ({n_all})"
    h_untouched = f"UNTOUCHED ({n_untouched})"
    h_tune = f"TUNE ({n_tune})"
    h_holdout = f"HOLDOUT ({n_holdout})"

    print(f"\n{'='*75}")
    print("                      EVALUATION BENCHMARK REPORT                    ")
    print(f"{'='*75}")
    print(f"{'Metric':<28} | {h_all:<10} | {h_untouched:<14} | {h_tune:<10} | {h_holdout:<10}")
    print("-" * 75)
    print(f"{'Recall@5':<28} | {m_all['recall_5']:>8.2f}% | {m_untouched['recall_5']:>12.2f}% | {m_tune['recall_5']:>8.2f}% | {m_holdout['recall_5']:>8.2f}%")
    print(f"{'Recall@10':<28} | {m_all['recall_10']:>8.2f}% | {m_untouched['recall_10']:>12.2f}% | {m_tune['recall_10']:>8.2f}% | {m_holdout['recall_10']:>8.2f}%")
    print(f"{'MRR (Mean Recip. Rank)':<28} | {m_all['mrr']:>8.4f}  | {m_untouched['mrr']:>12.4f}  | {m_tune['mrr']:>8.4f}  | {m_holdout['mrr']:>8.4f}")
    print(f"{'Gate Pass Rate':<28} | {m_all['gate_pass_rate']:>8.2f}% | {m_untouched['gate_pass_rate']:>12.2f}% | {m_tune['gate_pass_rate']:>8.2f}% | {m_holdout['gate_pass_rate']:>8.2f}%")
    print(f"{'False Abstention Rate':<28} | {m_all['false_abstention_rate']:>8.2f}% | {m_untouched['false_abstention_rate']:>12.2f}% | {m_tune['false_abstention_rate']:>8.2f}% | {m_holdout['false_abstention_rate']:>8.2f}%")
    print(f"{'Abstention Accuracy':<28} | {m_all['abstention_acc']:>8.2f}% | {m_untouched['abstention_acc']:>12.2f}% | {m_tune['abstention_acc']:>8.2f}% | {m_holdout['abstention_acc']:>8.2f}%")
    print(f"{'End-to-End Correctness':<28} | {m_all['e2e_acc']:>8.2f}% | {m_untouched['e2e_acc']:>12.2f}% | {m_tune['e2e_acc']:>8.2f}% | {m_holdout['e2e_acc']:>8.2f}%")
    print(f"{'='*75}")

    def avg_lat(vals):
        return sum(vals) / len(vals) if vals else 0.0

    print(f"\n{'='*75}")
    print("                     PER-STAGE LATENCY BREAKDOWN                     ")
    print(f"{'='*75}")
    if latencies["rewrite"]:
        print(f"  Stage 0 : Conversational Rewriting (LLM)   : {avg_lat(latencies['rewrite']):>8.2f} ms")
    print(f"  Stage 1 : Domain Query Normalization       : {avg_lat(latencies['norm']):>8.2f} ms")
    print(f"  Stage 2a: Query Embedding Generation       : {avg_lat(latencies['embed']):>8.2f} ms")
    print(f"  Stage 2b: Vector ANN Search (pgvector SQL) : {avg_lat(latencies['search_vec_sql']):>8.2f} ms")
    print(f"  Stage 2c: Keyword Search (FTS SQL)         : {avg_lat(latencies['search_fts_sql']):>8.2f} ms")
    print(f"  Stage 2d: Reciprocal Rank Fusion (RRF)     : {avg_lat(latencies['search_rrf']):>8.2f} ms")
    print(f"  Stage 3 : Cross-Encoder Reranking          : {avg_lat(latencies['rerank']):>8.2f} ms")
    print(f"  Stage 4 : Confidence Gating                : {avg_lat(latencies['gate']):>8.2f} ms")
    if latencies["gemini_check"]:
        print(f"  Stage 5 : Gemini Evidence Verification     : {avg_lat(latencies['gemini_check']):>8.2f} ms")
    print("  -------------------------------------------------------------------")
    print(f"  Total Retrieval Pipeline Avg Latency       : {avg_lat(latencies['total']):>8.2f} ms")
    print(f"  Total Wall Clock Time                      : {total_wall_sec:>8.2f} s")
    print(f"{'='*75}\n")

    return {
        "all": m_all,
        "untouched": m_untouched,
        "tune": m_tune,
        "holdout": m_holdout,
        "latencies": {k: avg_lat(v) for k, v in latencies.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="local", choices=["local", "jina"])
    parser.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--rerank-mode", default="natural", choices=["natural", "legacy"])
    parser.add_argument("--threshold", type=float, default=0.40)
    parser.add_argument("--gemini-check", action="store_true", default=False)
    args = parser.parse_args()

    eval_file = Path(__file__).resolve().parent / "eval_set.json"
    asyncio.run(
        run_evaluation(
            eval_set_path=eval_file,
            provider=args.provider,
            model_name=args.model,
            rerank_mode=args.rerank_mode,
            gate_threshold=args.threshold,
            enable_gemini_check=args.gemini_check,
        )
    )
