with open("backend/retrieval/hybrid_search.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """        # 1. First attempt: If department intent is recognized, filter by department
        if target_depts:
            vector_results = await self.vector_searcher.search(
                session=session,
                query=v_query,
                top_k=candidate_k,
                allowed_statuses=allowed_statuses,
                departments=target_depts,
                include_superseded=effective_superseded,
            )
            keyword_results = await self.keyword_searcher.search(
                session=session,
                query=k_query,
                top_k=candidate_k,
                allowed_statuses=allowed_statuses,
                departments=target_depts,
                include_superseded=effective_superseded,
            )

        # 2. Resilient fallback: If no department intent OR filtered search returned 0 results,
        # perform unconstrained search so campus-wide notices are never missed
        if not vector_results and not keyword_results:
            vector_results = await self.vector_searcher.search(
                session=session,
                query=v_query,
                top_k=candidate_k,
                allowed_statuses=allowed_statuses,
                departments=None,
                include_superseded=effective_superseded,
            )
            keyword_results = await self.keyword_searcher.search(
                session=session,
                query=k_query,
                top_k=candidate_k,
                allowed_statuses=allowed_statuses,
                departments=None,
                include_superseded=effective_superseded,
            )

        return self.reciprocal_rank_fusion(
            vector_results=vector_results,
            keyword_results=keyword_results,
            top_k=top_k,
        )"""

replacement = """        # Phase 1b: Unconstrained candidate retrieval across corpus so college-wide circulars
        # and departmental notices are never missed. Department intent is applied as a soft
        # RRF ranking boost rather than a rigid SQL WHERE filter.
        vector_results = await self.vector_searcher.search(
            session=session,
            query=v_query,
            top_k=candidate_k,
            allowed_statuses=allowed_statuses,
            departments=None,
            include_superseded=effective_superseded,
        )
        keyword_results = await self.keyword_searcher.search(
            session=session,
            query=k_query,
            top_k=candidate_k,
            allowed_statuses=allowed_statuses,
            departments=None,
            include_superseded=effective_superseded,
        )

        return self.reciprocal_rank_fusion(
            vector_results=vector_results,
            keyword_results=keyword_results,
            top_k=top_k,
            target_departments=target_depts,
        )"""

assert target in text, "Target block not found in hybrid_search.py"
new_text = text.replace(target, replacement)
with open("backend/retrieval/hybrid_search.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("hybrid_search.py successfully updated to unconstrained search with soft RRF boost!")
