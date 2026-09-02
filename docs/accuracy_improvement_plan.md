# EduSync: Accuracy Improvement & RAG Optimization Implementation Plan

**Document Version:** 1.0  
**Target Milestone:** RAG Precision & Accuracy Enhancement (Phase 4 Optimization)  
**Location:** `/docs/accuracy_improvement_plan.md`  
**Companion Documents:** `EduSync_PRD.md`, `EduSync_Technical_Design_Document.md`, `AGENTS.md`  

---

## 1. Executive Summary & Target Metrics

EduSync is an institutional RAG chatbot delivering verified answers from Engineering College Ajmer (ECA) circulars, notices, exam timetables, and fee structures. High precision and zero hallucinations are strict non-negotiable requirements.

### Target Performance Benchmarks

| Metric | Current Baseline | Target Benchmark | Verification Method |
| :--- | :--- | :--- | :--- |
| **Retrieval Recall@5** | ~74% | **$\ge$ 92%** | Golden fixture query suite (`eval_questions.json`) |
| **Answer Faithfulness (Grounding)** | ~86% | **$\ge$ 98%** | Automated LLM-as-a-judge context verification |
| **Notice Serial/Date Exact Match** | ~78% | **$\ge$ 99%** | Trigram & BM25 exact pattern matching |
| **Hallucination / Guess Rate** | < 4% | **0.0%** | Strict confidence gate fallback enforcement |
| **End-to-End Latency (p95)** | ~2.8s | **$\le$ 1.8s** | FastAPI async pipeline + warm client pools |

---

## 2. Architecture Overview: Accuracy Enhancement Pipeline

```
                              [ Student Query ]
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ 1. Query Understanding    │
                        │  - Institutional Synonyms │
                        │  - Serial Number Parser   │
                        │  - Intent / Dept Filter   │
                        └─────────────┬─────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
   ┌──────────────────────────┐              ┌──────────────────────────┐
   │ 2a. Dense Vector Search  │              │ 2b. Full-Text BM25       │
   │  - pgvector Cosine Sim   │              │  - tsvector exact match  │
   │  - Contextual Embeddings │              │  - Notice S.No / Trigram │
   └─────────────┬────────────┘              └─────────────┬────────────┘
                 └────────────────────┬────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │ 3. Dynamic RRF Fusion     │
                        │  - Adaptive Alpha Weight  │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ 4. Cross-Encoder Reranker │
                        │  - Deep Query-Chunk Score │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │ 5. Trust & Confidence Gate│
                        │  - Score < Threshold?     │
                        └──────┬─────────────┬──────┘
                   Yes (Low)   │             │  No (High Confidence)
             ┌─────────────────┘             └──────────────────┐
             ▼                                                  ▼
   ┌───────────────────┐                              ┌───────────────────┐
   │ Fallback Response │                              │ Grounded LLM Gen  │
   │ (Safe Disclaimer) │                              │ (Clean Markdown)  │
   └───────────────────┘                              └───────────────────┘
```

---

## 3. Phase-by-Phase Technical Implementation Plan

---

### Phase 1 — Query Understanding & Institutional Expansion
**Goal:** Prevent retrieval misses caused by student colloquialisms, acronyms, and vague queries.

#### 1.1 Institutional Synonym & Acronym Expander
* **Component:** `backend/retrieval/query_expander.py` [NEW]
* **Implementation:**
  * Build an in-memory dictionary mapping college-specific shorthand to formal institutional phrases:
    * `"mid sem"` $\rightarrow$ `"mid-term examination / mid semester examination / test"`
    * `"back exam" / "back paper"` $\rightarrow$ `"back examination / re-evaluation / mercy exam / backlog"`
    * `"sliding"` $\rightarrow$ `"internal sliding / branch change / department transfer office order"`
    * `"BTU" / "RTU"` $\rightarrow$ `"Bikaner Technical University / Rajasthan Technical University"`
    * `"HOD" / "Proctor"` $\rightarrow$ `"Head of Department / Chief Proctor Office / Proctorial Section"`
  * Expand queries dynamically before sending to vector search and keyword search.

#### 1.2 Notice Serial Number & Date Intent Detection
* **Component:** `backend/retrieval/query_expander.py`
* **Implementation:**
  * Use Regex detection for notice serial numbers (e.g., `2026WEB\d+` or `ECA/Proctor/\d+`) and date patterns (`\d{4}-\d{2}-\d{2}`, `\d{1,2}/\d{1,2}/\d{2,4}`).
  * If a serial number or date is detected, set `keyword_weight = 1.8` and `vector_weight = 0.8` in RRF fusion to prioritize exact identifier lookup.

---

### Phase 2 — Ingestion & Contextual Chunking Upgrades
**Goal:** Ensure chunks retain complete document identity and tabular structural integrity.

#### 2.1 Contextual Retrieval (Title & Metadata Prepending)
* **Component:** `backend/ingestion/chunker.py` [MODIFY]
* **Implementation:**
  * Prepend document metadata directly to every chunk's text representation prior to generating embeddings:
    ```python
    contextual_header = (
        f"Notice: {doc_title} | Department: {department} | "
        f"Category: {category} | Date: {notice_date}\n"
    )
    full_embed_text = f"{contextual_header}\n{chunk_text}"
    ```
  * *Why:* Eliminates fragmented orphan chunks (e.g. standalone tables of dates with no department name) that fail dense vector retrieval.

#### 2.2 Table & Timetable Preservation Chunker
* **Component:** `backend/ingestion/chunker.py`
* **Implementation:**
  * Detect Markdown and HTML tables in circulars.
  * Serialize tables with dual representations:
    1. Clean GitHub-flavored Markdown table.
    2. Linearized row statements (e.g. `"Date: 12-Apr-2026, Branch: CSE, Subject: Compiler Design, Shift: Morning"`).
  * Ensure tables are never split mid-row across chunk boundaries.

#### 2.3 Scanned Notice OCR Optimization
* **Component:** `backend/ingestion/fetchers/pdf_fetcher.py` [MODIFY]
* **Implementation:**
  * Incorporate image binarization and adaptive thresholding for scanned Hindi/English college notices before running OCR.
  * Clean whitespace artifacts and normalize Unicode date formats (`-`, `/`, `.`).

---

### Phase 3 — Hybrid Search & Reranking Optimization
**Goal:** Deliver top-ranked relevant chunks with high precision to the LLM context.

#### 3.1 Adaptive Reciprocal Rank Fusion (RRF)
* **Component:** `backend/retrieval/hybrid_search.py` [MODIFY]
* **Implementation:**
  * Introduce query-aware adaptive weights:
    * Standard conversational query: `vector_weight=1.0`, `keyword_weight=1.0`, `rrf_k=60`.
    * Exact keyword / ID / Date query: `vector_weight=0.7`, `keyword_weight=1.6`, `rrf_k=40`.
  * Deduplicate chunks at the document level to prevent 4 chunks of the same notice from monopolizing the context window.

#### 3.2 High-Performance Cross-Encoder Reranker
* **Component:** `backend/retrieval/reranker.py` [MODIFY]
* **Implementation:**
  * Standardize cross-encoder scoring with calibrated sigmoid normalization.
  * Support pluggable reranker backends:
    * Primary default: `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast CPU inference).
    * High-accuracy GPU/Cloud option: `BAAI/bge-reranker-base`.
  * Dynamic Top-K selection: Return top 3–4 chunks only if score is within 15% of the top chunk's score.

#### 3.3 Conflict Resolution & Recency Boosting
* **Component:** `backend/retrieval/vector_search.py` & `backend/ingestion/conflict_detector.py`
* **Implementation:**
  * Exclude all documents flagged in the `conflicts` table from active search indices until resolved.
  * Apply a mild recency decay multiplier (`exp(-0.005 * days_old)`) for general queries unless a specific past date is explicitly requested.

---

### Phase 4 — Prompt Engineering, Grounding & Trust Guardrails
**Goal:** Zero hallucination answers with high-quality Markdown formatting.

#### 4.1 Grounded Generation System Prompt
* **Component:** `backend/api/routes/chat.py` & `backend/retrieval/generator.py` [MODIFY]
* **Implementation:**
  * Enforce strict negative constraints:
    * *"Answer exclusively using the verified official document excerpts."*
    * *"If a date, deadline, or fee is not explicitly stated in the excerpts, state clearly that it is not available in current circulars."*
    * *"Never speculate, extrapolate, or estimate unverified details."*
  * Enforce output formatting: Clean Markdown (`##` titles, `**bold**` key facts, bullet points, clean links).

#### 4.2 Calibrated Confidence Gating
* **Component:** `backend/retrieval/confidence_gate.py`
* **Implementation:**
  * Baseline `CONFIDENCE_THRESHOLD = 0.55` (configurable via `.env`).
  * If top rerank score < threshold $\rightarrow$ Instant fallback message + suggest contacting the respective department office.
  * Never bypass or lower the threshold arbitrarily.

---

### Phase 5 — Automated Evaluation Harness & Continuous Benchmark
**Goal:** Quantify accuracy improvements and prevent regressions.

#### 5.1 Golden Evaluation Suite (`eval_questions.json`)
* **Component:** `backend/tests/test_evaluation_harness.py` [NEW]
* **Implementation:**
  * Curate 100 benchmark questions across 5 institutional categories:
    1. Examination Schedules & Timetables (25 questions)
    2. Fee Structures & Payment Deadlines (25 questions)
    3. Proctorial & Anti-Ragging Circulars (20 questions)
    4. Branch Change / Internal Sliding Orders (15 questions)
    5. Syllabus & Academic Ordinances (15 questions)
  * Automate metrics calculation:
    * **Context Recall@K**: Did top chunks contain the ground-truth document ID?
    * **Faithfulness Score**: Ratio of generated claims directly supported by the context chunks.
    * **Answer Relevance**: Semantic similarity between generated answer and reference ground-truth.

#### 5.2 CI Quality Gate
* **Component:** `.github/workflows/ci.yml` [MODIFY]
* **Implementation:**
  * Add automated evaluation test step running against the fixture dataset.
  * Fail CI if retrieval recall drops below 90% or fallback integrity fails.

---

## 4. Implementation Schedule & RACI Matrix

| Phase | Milestone / Deliverables | Timeline | Owner | Reviewer |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | Query Expander & Serial Number Parser | Days 1–3 | Retrieval Engineer | Backend Lead |
| **Phase 2** | Contextual Chunker & Table Serialization | Days 4–7 | Ingestion Engineer | Tech Lead |
| **Phase 3** | Adaptive RRF & Reranker Calibration | Days 8–11 | Retrieval Engineer | ML Lead |
| **Phase 4** | Prompt Grounding & Confidence Gate Tuning | Days 12–14 | Backend API Engineer | Product Lead |
| **Phase 5** | 100-Question Evaluation Harness & CI Integration | Days 15–16 | QA / Evaluation Lead | All Hands |

---

## 5. Verification & Validation Checklist

Before marking the accuracy improvement milestone as completed:

- [ ] `pytest backend/tests/test_evaluation_harness.py` passes with $\ge 90\%$ Recall@5.
- [ ] Ingestion pipeline runs hash-diff updates with contextual metadata prepending.
- [ ] Tables and timetables render without broken rows or fragmented data.
- [ ] Outdated circulars marked as conflicts are excluded from retrieval results.
- [ ] Low-confidence queries cleanly trigger fallback messages without hallucinated answers.
- [ ] CI pipeline (`.github/workflows/ci.yml`) passes all lint, format, and evaluation checks.
