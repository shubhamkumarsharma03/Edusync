import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from api.routes.chat import generate_llm_answer_async
from db.session import async_session_maker
from retrieval.confidence_gate import ConfidenceGate
from retrieval.hybrid_search import HybridSearcher
from retrieval.query_rewriter import query_rewriter
from retrieval.reranker import CrossEncoderReranker


async def main():
    items = json.load(
        open(
            Path(__file__).resolve().parent.parent / "eval" / "eval_set.json",
            encoding="utf-8",
        )
    )[55:]
    searcher = HybridSearcher()
    reranker = CrossEncoderReranker()
    gate = ConfidenceGate(threshold=0.40)

    async with async_session_maker() as session:
        for item in items:
            q = item["query"]
            h = item.get("history")
            search_q = q
            if h:
                rw = await query_rewriter.rewrite(q, h)
                if rw.is_rewritten:
                    search_q = rw.standalone_query

            chunks = await searcher.search(session, search_q, top_k=20)
            reranked = await reranker.arerank(search_q, chunks, top_k=10)
            gate_res = gate.evaluate(reranked)
            ctx = "\n".join([c.content[:2000] for c in reranked[:3]])
            llm_res = await generate_llm_answer_async(search_q, ctx)

            top_doc = str(reranked[0].document_id) if reranked else "none"
            exp_docs = item.get("expected_document_ids", [])
            hit = any(str(c.document_id) in exp_docs for c in reranked[:5])

            print(f"ID: {item['id']}")
            print(f"  Raw Query       : {q}")
            print(f"  Standalone Query: {search_q}")
            print(f"  Hit@5           : {hit} (Expected: {exp_docs})")
            print(f"  Gate Score      : {gate_res.top_score:.3f} (Passed: {gate_res.passed})")
            print(f"  LLM Answerable  : {llm_res.answerable}")
            print(f"  LLM Evidence    : {llm_res.evidence[:80]}")
            print(f"  LLM Answer      : {llm_res.answer[:120]}...\n")


if __name__ == "__main__":
    asyncio.run(main())

