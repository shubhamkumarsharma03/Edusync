# EduSync — Decision Log

This document records the significant architectural and technical decisions made during the EduSync project (self-updating RAG chatbot for Engineering College Ajmer). Each entry captures the decision, the context that drove it, alternatives considered, and consequences — so the reasoning survives beyond the team's memory and can be defended in review/viva.

Format: lightweight ADR (Architecture Decision Record). Newest decisions at the bottom. Status is one of `Proposed`, `Accepted`, `Superseded`.

---

## ADR-001: Use Retrieval-Augmented Generation (RAG), not custom pretraining or fine-tuning as the base approach

**Status:** Accepted

**Context:** EduSync needs to answer questions about institutional content (circulars, notices, syllabi, timetables) that changes frequently and must never be hallucinated.

**Decision:** Build a RAG system: retrieve relevant chunks from a vector store and ground LLM responses in them, with citations and confidence-gated fallback.

**Alternatives considered:**
- Custom LLM pretraining — rejected outright, infeasible at capstone scale and unnecessary for the problem.
- Fine-tuning as the primary mechanism — rejected as primary approach; fine-tuning can't cheaply absorb daily-changing institutional data.

**Consequences:** All architecture decisions below build on the RAG assumption. LoRA fine-tuning remains available as a late-stage (Sem 8) *experiment*, not a replacement for retrieval.

---

## ADR-002: Playwright as the mandatory fetcher for ecajmer.ac.in

**Status:** Accepted

**Context:** ecajmer.ac.in is a JavaScript-rendered SPA. Plain HTTP requests / BeautifulSoup return an empty shell with no usable content.

**Decision:** Use Playwright (headless browser) for all crawling/fetching from the college site.

**Alternatives considered:**
- `requests` + BeautifulSoup — rejected, returns empty DOM on this site.
- Scrapy with Splash — rejected as unnecessary added infra when Playwright covers the need directly.

**Consequences:** Crawling is heavier (browser overhead) but correct. No robots.txt exists and college permission was obtained, so this is not a compliance concern.

---

## ADR-003: Narrow crawl scope to CS/IT department before going site-wide

**Status:** Accepted

**Context:** Validating the full pipeline (fetch → parse → OCR → chunk → embed → index) against the entire site before validation increases blast radius of bugs and slows iteration.

**Decision:** Restrict initial crawl scope to CS/IT department pages. Expand site-wide only after the pipeline is validated end-to-end.

**Consequences:** Faster iteration cycles during Phase 3. Site-wide expansion is an explicit later milestone, not assumed to be a trivial flip of a config flag — new departments may surface new document formats/edge cases.

---

## ADR-004: OCR + table-aware extraction is the real ingestion problem, not HTML scraping

**Status:** Accepted

**Context:** A site audit revealed the majority of substantive content (circulars, timetables, syllabi) is distributed as scanned PDFs, not HTML text. Naive OCR (left-to-right, top-to-bottom) destroys table structure — and timetable meaning lives entirely in cell position (day × period × room/faculty).

**Decision:** Reframe the ingestion architecture around OCR and table-structure extraction as the primary challenge. Extracted tables are normalized into natural-language row statements (e.g., "On Monday, period 3, CS301 is taught by Prof. X in Room 204") *before* chunking and embedding — not fed to the embedder as raw grid text.

**Alternatives considered:**
- Treat this as a standard HTML-scraping problem — rejected after the audit; would silently corrupt timetable/tabular data.
- Feed OCR'd tables directly into the chunker without normalization — rejected; loses cell-position semantics that carry the actual meaning.

**Consequences:** Ingestion pipeline complexity shifted meaningfully toward document parsing. OCR engine choice (see ADR-007) became a first-class decision and a candidate ablation axis.

---

## ADR-005: PostgreSQL + pgvector for storage and vector search

**Status:** Accepted

**Context:** EduSync's target scale is modest — roughly 1,500 documents, 15K–30K vectors.

**Decision:** Use PostgreSQL with the pgvector extension for both relational metadata and vector similarity search, rather than a dedicated vector database.

**Alternatives considered:**
- Dedicated vector DBs (Pinecone, Weaviate, Qdrant, Milvus) — rejected as primary choice; unnecessary operational overhead at this scale, and adds a second system to keep in sync with relational metadata. Retained as a possible ablation/comparison axis, not a requirement.

**Consequences:** Single database to operate and back up. Retrieval logic is encapsulated behind an abstract `VectorStore` interface (`upsert()`, `search()`, `delete()`) specifically so a future migration to a dedicated vector DB — if ever needed — doesn't ripple through the rest of the codebase.

---

## ADR-006: CPU-only PyTorch, no CUDA dependency

**Status:** Accepted

**Context:** Deployment target has no GPU. A Docker build issue surfaced this concretely: pulling the default PyTorch wheel dragged in the full GPU/CUDA stack, bloating the image and risking runtime mismatches.

**Decision:** Install the CPU-only PyTorch wheel explicitly *before* the rest of `requirements.txt` in the Dockerfile, so pip resolves subsequent packages against the CPU build instead of pulling GPU variants.

**Consequences:** Any OCR/embedding library considered for the pipeline must have a viable CPU-only path — this directly eliminated GPU-only OCR tooling from consideration (see ADR-007) and constrains future model choices (e.g., LoRA fine-tuning experiments must budget for CPU-only training/inference or a separate one-off GPU environment outside the deployment target).

---

## ADR-007: OCR/document-parsing engine — PaddleOCR PP-StructureV3 as default, Docling and Tesseract as alternatives

**Status:** Accepted (default), other options retained as ablation axis

**Context:** Following ADR-004, the pipeline needs an OCR/table-extraction engine that (a) preserves table structure, (b) runs CPU-only (ADR-006).

**Decision:** Use PaddleOCR PP-StructureV3 as the default ingestion engine. Keep Docling + Granite-Docling-258M and Tesseract as alternatives — Docling for stronger performance on structured documents, Tesseract as a lightweight fallback.

**Consequences:** This three-way choice was deliberately kept open as a planned ablation axis (PaddleOCR vs. Docling vs. Tesseract) rather than settled permanently, since it's a natural publication-quality comparison for the capstone's academic angle.

---

## ADR-008: Hybrid retrieval (BM25 + semantic) with cross-encoder reranking and confidence gating

**Status:** Accepted

**Context:** Pure semantic search alone can miss exact-match queries (course codes, specific names/numbers) that keyword search handles well; conversely pure keyword search misses paraphrased queries.

**Decision:** Combine BM25 (keyword) and semantic (embedding) search, rerank candidates with a cross-encoder, and gate final responses behind a confidence threshold — returning an explicit "I don't have confident information on this" fallback rather than a hallucinated answer when confidence is low.

**Consequences:** Higher retrieval quality at the cost of added pipeline stages (reranking pass). Confidence gating is central to the project's core goal of avoiding hallucination and is treated as non-negotiable, not a nice-to-have.

---

## ADR-009: LoRA fine-tuning is an optional Sem 8 experiment, not a core deliverable

**Status:** Proposed

**Context:** The core system is RAG-based (ADR-001). There is academic value in comparing static RAG vs. self-updating RAG vs. a fine-tuned variant.

**Decision:** Treat LoRA fine-tuning as an optional, late-stage extension for Semester 8, contingent on time/resources after the core self-updating RAG pipeline is complete. Not a dependency for the primary deliverable.

**Consequences:** Feeds into the planned ablation study (static RAG vs. self-updating RAG vs. fine-tuned model) as one axis, alongside the OCR engine comparison (ADR-007) as the second axis.

---

## ADR-010: Figure/diagram generation via FigureLabs.ai (GPT Image 2)

**Status:** Accepted

**Context:** The project needs a system architecture diagram, graphical abstract, and ingestion flowchart for the synopsis/report and presentation materials.

**Decision:** Generate these via FigureLabs.ai using the GPT Image 2 model, Flat style, 16:9 aspect ratio, navy/gray palette for visual consistency. Export SVG for archival and high-resolution PNG for embedding in documents; JPG avoided due to compression artifacts on diagram text/labels.

**Consequences:** Consistent visual style across all three figures and future figures added later.

---

## ADR-011: Native / Non-Docker Local Development with PostgreSQL + pgvector

**Status:** Accepted

**Context:** Running application processes (FastAPI, Vite, Celery worker) directly on the host OS provides fast iteration and immediate debugging without Docker container overhead. At the same time, maintaining database schema and vector search parity between local development and production avoids subtle dialect bugs.

**Decision:**
1. **Unified Storage (PostgreSQL + pgvector):** Use PostgreSQL with the `pgvector` extension across both local development and production. Developers run PostgreSQL locally (or on localhost) and execute migrations via Alembic.
2. **Native Application Execution:** Run the FastAPI backend (`uvicorn`) and React frontend (`npm run dev`) directly on the host operating system using standard Python 3.11+ and Node.js 20+.
3. **Background Ingestion Execution:** In local development, execute background ingestion in-process via Celery eager mode (`CELERY_TASK_ALWAYS_EAGER=true`) or async background tasks, eliminating the hard requirement for an external Redis daemon.
4. **Containerization for Deployment:** Docker and Docker Compose remain supported for containerized staging/production deployments and CI environments.

**Consequences:** Complete storage and vector query parity between dev and prod, fast host-based development loops, and zero container overhead for daily coding.

---

## ADR-012: PDF-Centric Incremental Ingestion Strategy for ecajmer.ac.in

**Status:** Accepted

**Context:** Analysis of the institutional website (`ecajmer.ac.in`) indicates that ~95% of actionable knowledge (timetables, fee payment schedules, examination circulars, syllabus handbooks, and administrative announcements) is published as downloadable documents—primarily PDFs. New notices and revised PDFs are uploaded on a daily/frequent basis to the home page and department notice boards, while static HTML pages change less frequently (weekly or every 10 days).

**Decision:**
1. **Notice Board & Home Page Watcher:** Design the Playwright crawler to prioritize polling the announcement feeds and notice boards of `ecajmer.ac.in` on a configurable schedule (default every 6 hours).
2. **Incremental PDF Hash Ingestion:** As new PDFs are uploaded, compute SHA-256 content hashes immediately upon download. Existing PDFs from earlier dates hit the hash cache and are skipped (0 embedding cost), while only new or revised PDFs of the day undergo parsing and vector embedding.
3. **Table & Notice Normalization:** PDF parsing will prioritize table-structure preservation (ADR-004) to prevent timetable and fee-table semantic corruption.
4. **Revision & Stale Handling:** When a new notice supersedes an older notice of the same type/department, the earlier document's chunks are marked `stale` to prevent obsolete information retrieval.

**Consequences:** The ingestion engine operates with minimal compute overhead while guaranteeing near real-time synchronization with daily college document drops.

---

## ADR-013: Baidu PaddleOCR-VL with Persistent SHA-256 Markdown Cache for Document Parsing

**Status:** Accepted (supersedes ADR-007 default)

**Context:** Standard text extraction fails on scanned circulars, while naive OCR produces unstructured plain text that strips Markdown table syntax and heading semantics. Furthermore, re-running deep-learning OCR repeatedly during development or sync runs is computationally redundant.

**Decision:**
1. **Baidu PaddleOCR-VL:** Adopt Baidu PaddleOCR-VL as the primary OCR engine. It converts PDF pages into structured Markdown with native Markdown tables (`| ... |`), preserved column alignment, and hierarchical headings (`#`, `##`, `###`).
2. **Persistent SHA-256 Markdown Cache:** Hash raw PDF contents using SHA-256 and cache the resulting Markdown in `.cache/ocr_markdown/{hash}.md`. If a document was previously parsed, OCR is skipped completely (sub-millisecond cache hits).
3. **PyMuPDF Native Text Bypass:** If a PDF already contains high-density native text layers and no raster images, extract native text directly before invoking OCR.

**Consequences:** High-fidelity document structure preservation, native table support, and zero redundant compute during ingestion.

---

## ADR-014: BAAI/bge-m3 1024-Dimension Local Embeddings, Structure-Aware Breadcrumb Chunking, and Intent-Routed Hybrid Search

**Status:** Accepted

**Context:** Institutional engineering documents contain complex multi-level hierarchies (e.g. `Engineering College Ajmer > Academic Section > III Semester Rules`) and tables. The previous 384-dimensional model (`all-MiniLM-L6-v2`) had a restrictive 256-token context window and struggled with Hindi/English bilingual notices and long Markdown tables.

**Decision:**
1. **BAAI/bge-m3 Embedding Upgrade:** Adopt `BAAI/bge-m3` offering 1024 embedding dimensions, native bilingual (Hindi+English) retrieval, and an 8,192 token window.
2. **100% Offline Local Model Storage:** Cache model weights directly in `backend/models_cache/bge-m3` (`model.safetensors`, tokenizer, configs), eliminating Hugging Face Hub downloads and external API dependencies during runtime. Safely purge obsolete local models (`all-MiniLM-L6-v2`, `GOT-OCR-2.0-hf`).
3. **PostgreSQL pgvector Schema Migration:** Alter `chunks.embedding` from `vector(384)` to `vector(1024)` with an HNSW cosine index (`m=16, ef_construction=64`).
4. **Structure-Aware Markdown Chunking:** Implement heading stack traversal in `SemanticChunker` (`# > ## > ### > ####`). Prepend `[Context: Breadcrumbs]\n\n` to all child chunks so both dense vector embeddings and PostgreSQL full-text search tsvectors retain section context. Extract entities (`semester`, `notice_sno`, `academic_year`) into chunk metadata.
5. **Intent-Routed Hybrid Search:** Normalize student queries using `CollegeQueryNormalizer`. If a specific department intent is identified (e.g. "CSE", "Proctor Section"), pre-filter vector and keyword queries by department. If filtered search returns 0 results, gracefully fall back to unrestricted search to guarantee campus-wide notices are never missed.

**Consequences:** Substantially higher retrieval accuracy on shorthand student queries, atomic table preservation, zero hallucination via calibrated confidence gating (0.55), and completely offline model execution.

---

## ADR-015: Jina AI Search Foundation Integration (Embeddings v3, Reranker v2, Reader API, and Token Quota Tracker)

**Status:** Accepted

**Context:** While local CPU models (`bge-m3` and `ms-marco-MiniLM-L-6-v2`) provide complete offline reliability, high-concurrency cloud production and faster ingestion benefit from high-throughput API endpoints. Jina AI offers state-of-the-art search foundation models (`jina-embeddings-v3` and `jina-reranker-v2-base-multilingual`) with an identical 1024-dimension vector space, task-specific embedding adapters, multilingual cross-encoder reranking, and a generous 10,000,000 token free tier across all search foundation products on a single API key.

**Decision:**
1. **Zero-Migration Dimension Parity:** Use `jina-embeddings-v3` with `dimensions=1024`. Because EduSync's PostgreSQL schema is already standardized on `vector(1024)` (ADR-014), no schema change or database migration is required.
2. **Asymmetric Task Adapters:** Ingested document chunks are embedded using `task="retrieval.passage"`. Student query vectors are embedded using `task="retrieval.query"`, optimizing the asymmetric vector matching surface.
3. **Batching & Resilience:** Batch document chunk embedding calls in chunks of 32 using asynchronous `httpx.AsyncClient`. Retry automatically with exponential backoff on HTTP 429 and 5xx status codes.
4. **Multilingual Cross-Encoder Reranker:** Ingest hybrid search results into `jina-reranker-v2-base-multilingual`. Fetch top 20 candidate chunks via RRF, rerank down to top 5 items, and feed scores into `ConfidenceGate(threshold=0.55)`.
5. **Token Quota Awareness:** Implement `JinaTokenTracker` as a thread-safe singleton tracking cumulative embeddings and reranking tokens against Jina's 10,000,000 free-tier limit. Expose metrics via `GET /admin/jina-usage`.
6. **Seamless Fallback & Shared Key:** One API key (`JINA_API_KEY`) authenticates both embeddings and reranking. If `JINA_API_KEY` is not set or `EMBEDDING_PROVIDER="local"` / `RERANKER_PROVIDER="local"` is selected, the system transparently falls back to local CPU models with zero pipeline disruption.
7. **Jina Reader Support:** Provide `JinaReader` helper utilizing `https://r.jina.ai/` for direct URL-to-markdown conversion of college portals and documents without browser dependencies.

**Consequences:** Near-instantaneous query reranking latency, high-throughput non-blocking document ingestion, live token monitoring, zero hallucination via preserved confidence gating, and zero lock-in due to seamless local model fallbacks.

---

## ADR-016: Chronological Portal Ordering, Ground-Truth Title Persistence & Notice Metadata Synchronization

**Status:** Accepted

**Context:** On the admin dashboard explorer ("Stored in EduSync DB"), documents were previously ordered by `ingested_at DESC`. When an older historical notice (e.g., from 2025) was ingested or refreshed, it jumped to row 1 on page 1, breaking visual comparison against the live ECA college portal feed. Furthermore, notice titles were being extracted dynamically via regex matching headings from arbitrary chunks; due to random UUID sorting of chunk IDs, institutional letterheads (e.g., `# ENGINEERING COLLEGE AJMER`) were frequently surfaced as document titles instead of the actual circular title.

**Decision:**
1. **Schema Additions (`documents` table):** Add native columns `title` (Text), `notice_sno` (Text), `notice_date` (Date), and `portal_id` (Integer).
2. **Deterministic Compound Index:** Create database index `idx_documents_portal_order` on `(notice_date DESC NULLS LAST, notice_sno DESC NULLS LAST, portal_id DESC NULLS LAST)`.
3. **Portal Ground-Truth Title Ingestion:** Extract clean HTML anchor text and API title payloads (`entry["title"]`) during crawling in `ecajmer_fetcher.py`. Persist this clean title directly to `documents.title` during upsertion, bypassing noisy scanned PDF letterheads.
4. **Boilerplate Letterhead Filtering:** Implement `_clean_extracted_title()` to reject institutional headers (`ENGINEERING COLLEGE AJMER`, `GOVT. ENGINEERING COLLEGE`, `NOTICE`, `CIRCULAR`, `OFFICE ORDER`, `DEPARTMENT OF...`) from ever qualifying as notice titles.
5. **Admin Source Query Realignment:** In `list_source_documents`, sort records strictly by `Document.notice_date.desc().nullslast(), Document.notice_sno.desc().nullslast(), Document.portal_id.desc().nullslast(), Document.ingested_at.desc()`.

**Consequences:** The admin explorer now matches the official college portal listing 100% row-for-row. Any newly ingested notice from any historical date lands precisely in its correct chronological position, making manual and automated audits trivial.

---

## ADR-017: High-Precision Notice Ingestion: Page-Level Hybrid OCR, Boilerplate Stripping, and Model-Safe Contextual Chunking

**Status:** Accepted

**Context:** Scanned college notices contain significant structural noise: repetitive multi-line letterheads, page footers ("Page 1 of 2"), long administrative distribution lists ("Copy to: 1. Principal..."), and complex timetables. File-level OCR was unnecessarily slow for hybrid PDFs containing native text pages alongside scanned pages. Additionally, chunk splitting without table header repetition destroyed tabular relational semantics across chunk boundaries, and long notices risked exceeding embedding model sequence length limits.

**Decision:**
1. **Early SHA-256 Hash Short-Circuiting:** Compute SHA-256 binary content hashes immediately after downloading file bytes. If the hash matches an active stored record, bypass PyMuPDF parsing, rasterization, and OCR completely (sub-millisecond skip).
2. **Page-Level Hybrid PDF Parsing:** Evaluate text density per page. Pages with dense native text ($>40$ chars) and no raster images are extracted directly via PyMuPDF; pages with low density or large embedded images ($>300\times200$ px) route selectively to Baidu PaddleOCR-VL.
3. **Markdown Table Chunking with Header Repetition:** When splitting large multi-row tables across chunks, split strictly on row boundaries and repeat the Markdown table column headers (`| Col 1 | Col 2 |\n|---|---|`) at the top of every chunk.
4. **Institutional Boilerplate Stripping:** Use targeted regular expressions before chunking to strip repeated letterheads, page footers, and trailing `"Copy to: ..."` distribution lists, keeping provenance URLs intact.
5. **Contextual Header Injection & Token Budgeting:** Prepend a structured header `[Notice: <Title> | Ref: <S.No> | Date: <Date> | Dept: <Dept>]` to every chunk. Enforce a strict token budget ($\le 550$ tokens) with 50 tokens of safety headroom below the embedding model context limit. Avoid force-splitting short notices that fit within a single token window.
6. **Automatic Corrigendum & Revision Linking:** Detect keywords (`Revised`, `Corrigendum`, `Postponed`, `In continuation of`) and automatically link and supersede prior active circulars on the same topic in the same department.

**Consequences:** Drastically reduced ingestion time, zero token truncation, robust preservation of timetable/fee matrices, and elimination of outdated circulars outranking revisions during retrieval.

---

## ADR-018: Database Audit, Metadata Completeness, and Student Query Lifecycle Logging

**Status:** Accepted

**Context:** A comprehensive database audit across all 8 tables (`documents`, `chunks`, `departments`, `ingestion_sources`, `conflicts`, `notice_memory`, `queries_log`, `alembic_version`) revealed several metadata gaps:
1. `documents.owner` was 100% NULL (207/207 rows) because fetchers and upsert logic did not map department names to the owner field.
2. `chunks.original_content` was 83.6% NULL (450/538 rows) because migration `a1b2c3d4e5f6` added the column as nullable but did not backfill legacy chunks.
3. 4 portal index HTML documents had NULL `notice_sno` and `notice_date`.
4. `notice_memory` had 98 NULL departments and 97 NULL serial numbers/dates due to zero-shot LLM extraction failures on blurry PDF scans.
5. `queries_log` contained 0 rows because the `/chat` route did not persist inbound queries or citations.
6. 3 unresolved conflict rows locked 6 valid documents from retrieval.

**Decision:**
1. **Schema & Ingestion Hardening:**
   - In `upsert.py`, ensure `doc_owner` resolves with cascading fallback: `owner -> metadata.get("owner") -> metadata.get("department") -> metadata.get("source_section") -> departments.name lookup`.
   - In `upsert.py`, ensure `Chunk` instantiation explicitly populates `original_content = chunk_data.metadata.get("original_content") or chunk_data.content`.
   - In `notice_analyzer.py` and `supersession_resolver.py`, cascade department, notice serial number, and effective date lookups to ground-truth document metadata whenever LLM extraction returns empty.
2. **One-Time Data Backfill:**
   - Backfilled all 207 `documents.owner` rows from `departments.name`.
   - Backfilled all 450 `chunks.original_content` rows from `chunks.content` (stripping contextual header prefixes).
   - Backfilled all `notice_memory` metadata fields from `documents`.
   - Assigned structured identifiers to HTML portal documents (`TPO-INDEX`, `ACAD-PORTAL`, `MATHS-PORTAL`, `MANDATORY-DISCLOSURE`).
3. **Query Logging & Feedback:**
   - In `backend/api/routes/chat.py`, persist every query transaction to `queries_log` with question text, qualifying chunk UUIDs, answer text, and confidence scores.
   - Added `POST /chat/feedback` endpoint accepting `query_id` and `feedback` ("up" | "down") to support student feedback collection per PRD FR-15.
4. **Admin Conflict Resolution:**
   - Built `scripts/resolve_pending_conflicts.py` providing automated classification and audit notes for pending conflicts (e.g. Sem 3 vs Sem 7 fee notices verified non-conflicting; revised exam notices superseding older notices).

**Consequences:** 100% metadata completeness across all PostgreSQL tables, elimination of orphan/untyped records, active query audit logging in production, and zero risk of retrieval lockout.

---

## ADR-019: Admin Dashboard Operations, Conflict Invalidation (Drop Both), Manual Ingestion, and System Tools Sandbox

**Status:** Accepted

**Context:** Institutional administrators required deeper operational controls to manage notices without technical intervention:
1. Conflicting notices occasionally occur where *both* notices are erroneous or obsolete, requiring an action to "drop both" rather than choosing one authoritative document.
2. Urgent physical notices or circulars issued offline must be ingested immediately into RAG without waiting for website publication.
3. Operations teams needed diagnostic tools to evaluate retrieval scoring without polluting student query metrics, test external portal URL scrapers prior to scheduling, and trigger on-demand corpus syncs.
4. The `documents_status_check` constraint previously restricted status values to `('fresh', 'stale', 'conflicted', 'pending')`, which caused DB constraint violations when marking documents as archived.

**Decision:**
1. **Schema Migration:** Created migration `d4e5f6a7b8c9` updating `documents_status_check` to allow `'archived'` status.
2. **Conflict Resolution ("Drop Both" & Reopen):**
   - Added `POST /admin/conflicts/{id}/resolve` support for `archive_both` / `drop_both`, which marks all involved documents as `archived`, completely excluding both from student retrieval.
   - Added side-by-side text/chunk comparison modal (`GET /admin/conflicts/{id}/compare`).
   - Added conflict audit reopen action (`POST /admin/conflicts/{id}/reopen`).
3. **Manual Notice Ingestion & Metadata Editor:**
   - Implemented `POST /admin/documents/manual-upload` to chunk, embed, and store offline notices on the fly.
   - Implemented `PUT /admin/documents/{id}` for metadata editing (title, serial number, notice date, department).
   - Added multi-row selection with floating bulk action bar (bulk re-ingest, status update, bulk delete).
4. **System Tools & Analytics:**
   - Built `SystemToolsPanel` featuring RAG Diagnostic Playground (`POST /admin/tools/rag-playground`), database/pgvector latency monitor (`GET /admin/tools/health`), and manual corpus sync trigger (`POST /admin/tools/sync-all-sources`).
   - Added live source URL connectivity test (`POST /admin/sources/test-url`) directly inside the Add/Edit Source modal.
   - Added 3-tier confidence distribution visualization and CSV query log export.

**Consequences:** Administrators have end-to-end operational autonomy over document lifecycles, conflicts, emergency notices, and retrieval diagnostics while strictly preserving confidence gating and citation guarantees.

---

## ADR-020: Multi-Conversation Session Architecture, Student Account Partitioning, and Conversational Context Resolution

**Status:** Accepted

**Context:** The student chat interface previously stored a single in-memory transcript that was lost on reload and lacked conversation persistence, organization (pinned/archived/recents), and support for multiple student accounts. Furthermore, multi-turn follow-up queries required conversational context in the synthesis prompt so that the LLM could resolve references to previous turns while preserving grounded retrieval.

**Decision:**
1. **Database Schema & Server Sessions:** Created `chat_sessions` table via Alembic migration `e5f6a7b8c9d0`, indexing `(student_id, updated_at)` with fields for `title`, `is_pinned`, `is_archived`, and `messages` JSONB.
2. **REST API Endpoints:** Built `/chat/sessions` supporting full CRUD, active vs archived filtering, pin toggle, and archive toggle.
3. **Multi-User Partitioning & Local Storage:**
   - Client-side storage layer (`chatStorage.ts`) partitions conversation states by `student_id` (e.g. `edusync_chats_${studentId}`).
   - Provides immediate, zero-latency UI interaction (switching, pinning, archiving, renaming) combined with background PostgreSQL synchronization.
   - Profile switcher modal allows switching active student accounts on the fly without breaking other users' data.
4. **Conversational Memory in RAG:**
   - The query rewriter handles query standalone reformulation for hybrid search.
   - The answer generation pipeline (`generate_llm_answer_async`) accepts the last 4 dialogue turns and injects them as `RECENT CONVERSATION CONTEXT` into the prompt, enabling natural follow-up understanding while strictly preserving grounded factual constraints.
5. **ChatGPT Light Aesthetic:** Redesigned the student layout with a collapsible sidebar, primary "New chat" button, search filter, pinned notices section, recents list, archived drawer, and clean floating input bar.

**Consequences:** Students have a familiar ChatGPT-style conversation management workflow, follow-up queries are answered with full conversational context, and the architecture is prepared for institutional multi-user student authentication.

---

## ADR-021: Database Expansion for Multi-Student Registration, Relational Session Isolation, and Telemetry Improvement Layer

**Status:** Accepted / Planning

**Context:** The application requires true multi-user student support with registration, individual institutional credentials, and relational isolation of chat histories, pinned notices, and archives. Furthermore, to continuously improve RAG retrieval accuracy and institutional notice coverage, the database must capture actionable telemetry (knowledge gap tracking for unanswered questions, latency breakdowns, rewritten query effectiveness, and fine-grained student feedback).

**Decision:**
1. **Student Account Entity (`students`)**: Introduce a dedicated `students` table storing institutional identifiers (`college_roll_no`, `email`), academic context (`branch`, `semester`, `degree`), and secure password hashes (`password_hash`).
2. **Relational Session Binding**: Upgrade `chat_sessions.student_id` to a strict foreign key referencing `students(id)` with cascade deletion and composite indexes for fast chronological and pinned queries.
3. **Continuous Improvement Telemetry (`queries_log`, `knowledge_gaps`, `query_feedback`)**:
   - `queries_log`: Expanded with session ID, student ID, `raw_question`, `rewritten_question`, `detected_intent`, latency metrics (retrieval vs generation), and token counts.
   - `knowledge_gaps`: Automatically aggregates recurring queries where the confidence gate fell below 0.40, alerting institutional administrators to missing circulars.
   - `query_feedback`: Records specific issue tags (`outdated_date`, `wrong_info`, `missing_details`, `helpful`) rather than only binary signals.
4. **Context-Aware Retrieval**: The student's academic profile (`branch`, `semester`) will be injected into retrieval queries to personalize grounding without requiring students to repeat their department or semester in every prompt.
5. **No Dummy Data Guarantee**: The frontend will fetch all conversation lists and transcripts exclusively from PostgreSQL via authenticated REST endpoints.

**Consequences:** Enables secure institutional multi-tenancy, isolates personal chat histories and pinned circulars per student, eliminates client mock state, and provides the structured data needed to train and evaluate the RAG pipeline.

---

## Open / not yet decided

- Final decision on whether the ablation study (RAG variants × OCR engines) is scoped into the core capstone deliverable or treated as a stretch goal for the paper.
- Whether/when to expand crawl scope beyond CS/IT department site-wide (see ADR-003) — pending Phase 3 validation results.
- Whether a dedicated vector DB is worth benchmarking against pgvector as part of the ablation study, or left purely as a documented alternative (see ADR-005).

---

*Maintained alongside `EduSync_PRD.md`, `EduSync_Technical_Design_Document.md`, `implementation_plan.md`, and `AGENTS.md`. When a new architectural decision is made, add a new ADR entry here in the same pass as updating the other project documents.*