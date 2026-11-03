# EduSync - Retrieval Improvement Status & Resumption Guide

**Branch:** `nlp-query`  
**Base Branch:** `feat/fast-ingestion-ocr-cache` (clean at commit `80f1196`)  
**Latest Commit on `nlp-query`:** `d23ee8f` (`feat(retrieval): Phase 1 retrieval improvements, 3-tier confidence gate, FTS stored tsvector, and evaluation harness`)  
**Status Date:** November 2026  

---

## 1. Context & Objective

### Problem Statement
In the original baseline, students had to type wording almost identical to official college notices for the RAG chatbot to retrieve relevant context. Queries that were:
- Short (e.g., *"6 sem exam form last date?"*)
- Informal or in Hinglish (e.g., *"exam form kb tk bhrna h?"*, *"fine kitna lagega?"*)
- Paraphrased or misspelled
- Follow-up or multi-part questions

frequently failed retrieval or fell below the strict confidence gate (`CONFIDENCE_THRESHOLD = 0.82`), resulting in false fallbacks (*"I could not find any official college notice..."*).

### Non-Negotiable Rules & Constraints
Per `AGENTS.md` and project requirements:
1. **Trust Layer Intact:** Every answer must include verified source citations (`document`, `last_verified`, `url`).
2. **Confidence Gate:** Below-threshold retrievals must abstain and return an official fallback, never a hallucinated guess.
3. **Conflict Exclusion:** Contradicting or superseded notices in `conflicts` must remain excluded from retrieval.
4. **Change Detection:** Only modified chunks are re-embedded via content hashing; never re-embed the whole corpus blindly.
5. **Phase-by-Phase Verification:** Never claim metrics or tests pass without running evaluation scripts.

---

## 2. What Has Been Completed

### Phase 0: Diagnosis, Profiling & Baseline Harness
- **Diagnostic Findings:**
  - Hard department SQL filtering (`WHERE Department.name.in_(...)`) locked out multi-branch or general notices if a query casually mentioned words like *"me"* (matched as Mechanical Engineering).
  - Reranker cross-encoder received heavily bloated query strings (`query + regex synonyms`) rather than the student's natural phrasing, degrading cross-attention scores.
  - Full-text search was unindexed with strict English stemming, failing on Hindi/Hinglish terms (*sem*, *bharna*, *kb tk*).
  - High confidence cutoff (`0.82`) caused high false-abstention rates on legitimate matches.
- **Evaluation Benchmark (`eval/eval_set.json`):**
  - **55 total test queries:**
    - 35 answerable across real notices (exam dates, fee structures, workshops, sports, circulars).
    - 20 unanswerable queries (including 15 college near-misses such as MCA lateral entry, hostel wifi password, duplicate degree fee).
    - Stratified into **37 tune (2/3)** and **18 holdout (1/3)** splits.
- **Harness & Profiler (`eval/run_eval.py` & `eval/trace_failures.py`):**
  - Measures Recall@5, Recall@10, MRR, Gate Pass Rate, False Abstention Rate, Abstention Accuracy, and End-to-End Correctness.
  - Per-query failure tracer and latency profiler.

---

### Phase 1: High-Impact Algorithmic & Database Upgrades
1. **Natural Query to Reranker (`backend/api/routes/chat.py`):**
   - The cross-encoder reranker now receives the clean, unaltered natural student query (`query=query`), while the search layer receives normalizer entity hints.
2. **Soft Department RRF Boost (`backend/retrieval/hybrid_search.py`):**
   - Replaced rigid SQL `WHERE Department.name.in_(...)` filters with unconstrained candidate retrieval (`departments=None`).
   - Injected a soft **1.3x RRF multiplier** for chunks matching detected departments. College-wide notices are never locked out.
   - Fixed normalizer bug in `backend/retrieval/query_normalizer.py`: words like *"college me..."* or *"tell me..."* no longer trigger Mechanical Engineering department tags.
3. **PostgreSQL FTS Upgrade (`backend/alembic/versions/f1a2b3c4d5e6_fts_tsvector_gin_trgm.py`):**
   - Activated `pg_trgm` extension in PostgreSQL.
   - Added stored generated column `chunks.tsv` using the `simple` text dictionary (`to_tsvector('simple', content)`) with a dedicated GIN index.
   - Added GIN trigram index on `chunks.content`.
   - Updated `backend/retrieval/keyword_search.py` with `COLLEGE_GLOSSARY` (*sem* $\to$ *semester*, *bharna* $\to$ *submit/fill*, *kb tk* $\to$ *last date deadline*, *fine* $\to$ *late fee*) and OR-style ranked matching (`term1 | term2 | ...`).
4. **Calibrated Three-Tier Confidence Gate (`backend/retrieval/confidence_gate.py`):**
   - **Tier 1 (High Confidence $\ge 0.75$):** Answer directly with standard source citations.
   - **Tier 2 (Medium Confidence $0.40 - 0.75$):** Answer with an upfront student caveat:
     > `> ⚠️ *Note: This answer is based on related college notices, but please verify with the official circular or department coordinator.*`
   - **Tier 3 (Low Confidence $< 0.40$):** Abstain with official fallback message.
   - Updated `CONFIDENCE_THRESHOLD = 0.40` in `backend/api/config.py` and `.env`.
5. **`original_content` Separation (`backend/alembic/versions/a1b2c3d4e5f6_add_original_content_to_chunks.py`):**
   - Added `original_content: Text` column to `chunks` table.
   - Backfilled all 88 existing chunks by stripping leading `[Notice: ...]` enrichment tags, preserving pure original notice text for generation and citations.
6. **Query Embedding Cache & Local Reranker Latency Optimization:**
   - Added in-memory LRU query embedding cache (`DocumentEmbedder.get_cached_query_embedding`), dropping repeated query embedding latency from **941 ms to 0.003 ms**.
   - Made reranker provider configuration explicit and fail-loud (`RERANKER_PROVIDER=local` in `backend/api/config.py`).
   - Using local `cross-encoder/ms-marco-MiniLM-L-6-v2` (788 ms on CPU) avoids free-tier cloud rate limits (Jina 429 backoff).
7. **Test Suite Integrity:**
   - All **107 unit tests** in `backend/tests/` pass cleanly via `pytest`.

---

## 3. Evaluation Benchmark Results

Evaluated on local PostgreSQL with 25 ingested college notices (88 chunks) and local CPU reranker:

| Metric | Phase 0 Baseline | Phase 1 (Final on `nlp-query`) | Absolute Delta |
| :--- | :---: | :---: | :---: |
| **Recall@5** | 74.29% | **97.14%** | **+22.85%** |
| **Recall@10** | 80.00% | **97.14%** | **+17.14%** |
| **MRR (Mean Reciprocal Rank)** | 0.7571 | **0.9714** | **+0.2143** |
| **Gate Pass Rate (Answerable)** | 54.29% | **82.86%** | **+28.57%** |
| **False Abstention Rate** | 45.71% | **17.14%** | **-28.57%** |
| **Abstention Accuracy (Unanswerable)** | 100.00% | **90.00%** | (Pure score gate) |
| **End-to-End Correctness** | 56.36% | **83.64%** | **+27.28%** |

### Breakdown by Subsets:
- **Pure Untouched Subset (51 queries, excluding data/conflict fixes):**
  - **Recall@5:** `100.00%`
  - **MRR:** `1.0000`
  - **End-to-End Correctness:** `86.27%`
- **Holdout Split (18 queries):**
  - **Recall@5:** `100.00%`
  - **MRR:** `1.0000`
  - **Abstention Accuracy:** `100.00%`
  - **End-to-End Correctness:** `88.89%`

### Latency Breakdown (Per Query on CPU):
- Query Normalization: `0.38 ms`
- Query Embedding: `941.06 ms` (Cold) / `0.003 ms` (Cached)
- pgvector ANN SQL: `3.81 ms`
- FTS GIN SQL: `4.00 ms`
- RRF Fusion: `0.05 ms`
- Cross-Encoder Reranker: `788.29 ms`
- Confidence Gate: `0.06 ms`
- **Total Pipeline Latency:** ~`1.74 s` (Wall-clock time for 55 eval queries: 96.59 s)

---

## 4. Ingestion Bugs Resolved During Development

1. **`'Document' object has no attribute 'department'`:**
   - Fixed by adding `@property def department` to `backend/models/document.py` returning `self.department_rel.name`, with `lazy="selectin"` relationship.
2. **`ForeignKeyViolationError on notice_memory_superseded_by_fkey`:**
   - Fixed in `backend/ingestion/supersession.py`: flushed `record` before assigning `old.superseded_by = record.id`.
3. **Session Rollback on Error:**
   - Added `await session.rollback()` in `backend/ingestion/pipeline.py` and `backend/ingestion/tasks.py` so a single document failure does not invalidate the batch transaction.

---

## 5. What Is Left To Do (Roadmap for Next Session)

The next steps from the original user instructions are prioritized as follows:

### Task 1: In-Prompt Gemini Evidence Check (Phase 1 Refinement)
- **Status:** Prototyped and verified in `scripts/test_gemini_gate.py`. Not yet wired into production `backend/api/routes/chat.py`.
- **Goal:** In `generate_llm_answer_async`, prompt Gemini to return a structured JSON check:
  ```json
  {"answerable": true/false, "evidence": "direct quote or chunk reference", "answer": "..."}
  ```
- **Benefit:** Catches extreme lexical near-misses (e.g. `eval_43` asking about duplicate degree fees when the retrieved notice is about regular exam fees). Pushes unanswerable abstention accuracy from **90% to 100%**.

### Task 2: Ingest Full Notice Corpus & Recalibrate
- **Status:** Currently tested against 25 active notices (88 chunks).
- **Action:**
  - Run full ingestion across all 28 official active links configured in `IngestionSource` via `_run_fetch_all_sources_by_priority()` in `backend/ingestion/tasks.py`.
  - Report total ingested documents and chunk count.
  - Re-run `eval/run_eval.py` on the larger corpus to verify retrieval precision and gate calibration under realistic noise.

### Task 3: Phase 3 - Single-Call Query Rewriting & Follow-Up Handling
- **Status:** Not started (user explicitly paused Phase 2 RRF tuning and synthetic questions to proceed directly to Phase 3).
- **Action:**
  1. **Dataset Extension:** Add at least 8 multi-turn follow-up and ambiguous student question test cases to `eval/eval_set.json` (e.g. Turn 1: *"when is 3rd sem exam?"*, Turn 2: *"what is the last date without late fee?"*, Turn 3: *"is it extended?"*).
  2. **Query Rewriter Module (`backend/retrieval/query_rewriter.py`):**
     - Make a single structured LLM call passing student query + last $N$ conversation turns ($N=4$).
     - Output:
       ```json
       {
         "standalone_query": "Rewritten self-contained question",
         "search_queries": ["PostgreSQL tsquery / semantic query variations"],
         "needs_clarification": false,
         "entities": {"department": "...", "semester": "...", "category": "..."}
       }
       ```
  3. **Evaluation:** Rerun `eval/run_eval.py` and verify Recall@5 and MRR on conversational follow-ups.

---

## 6. How to Resume Work

### Environment Setup
Open PowerShell in `d:\Projects\EduSync`:
```powershell
# Ensure you are on the nlp-query branch:
git status
git checkout nlp-query

# Activate Python virtual environment:
.venv\Scripts\Activate.ps1
```

### Key Verification Commands
```powershell
# 1. Run unit test suite (should be 107 passed):
pytest backend/tests/ -v

# 2. Run the retrieval & gating evaluation harness:
python eval/run_eval.py

# 3. Inspect failures on any run:
python eval/trace_failures.py

# 4. Start local backend server:
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

### Key Files Reference
- Evaluation Set: `eval/eval_set.json`
- Evaluation Runner: `eval/run_eval.py`
- Hybrid Search & Soft Boosts: `backend/retrieval/hybrid_search.py`
- Keyword Search & Glossary: `backend/retrieval/keyword_search.py`
- Confidence Gate & Caveat: `backend/retrieval/confidence_gate.py`
- Chat Route: `backend/api/routes/chat.py`
- Embedder Cache: `backend/ingestion/embedder.py`
- Reranker: `backend/retrieval/reranker.py`
