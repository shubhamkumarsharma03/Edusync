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

## Open / not yet decided

- Final decision on whether the ablation study (RAG variants × OCR engines) is scoped into the core capstone deliverable or treated as a stretch goal for the paper.
- Whether/when to expand crawl scope beyond CS/IT department site-wide (see ADR-003) — pending Phase 3 validation results.
- Whether a dedicated vector DB is worth benchmarking against pgvector as part of the ablation study, or left purely as a documented alternative (see ADR-005).

---

*Maintained alongside `EduSync_PRD.md`, `EduSync_Technical_Design_Document.md`, `implementation_plan.md`, and `AGENTS.md`. When a new architectural decision is made, add a new ADR entry here in the same pass as updating the other project documents.*