# The Blueprint — Implementation Plan
## EduSync: Step-by-Step Technical Build Plan

**Version:** 1.0
**Companion docs:** `EduSync_PRD.md`, `EduSync_Technical_Design_Document.md`, `AGENTS.md`
**Last Updated:** July 25, 2026

This plan sequences the build so nothing later depends on something not yet built — project scaffolding first, then the database (everything else reads/writes to it), then backend services (ingestion → retrieval → API), then frontend. Each phase lists concrete tasks, exit criteria, and which FR/milestone from the PRD it satisfies.

---

## Phase 0 — Prerequisites & Team Setup

**Goal:** Everyone can run the project locally without Docker before any feature code is written.

- [x] Create GitHub repo, add `AGENTS.md`, `docs/` folder with PRD + TDD copied in
- [x] Assign the 4 roles (per TDD/PRD): Ingestion owner, Retrieval/Vector DB owner, Backend API/Evaluation owner, Frontend/UX owner
- [x] Set up `.env.example` listing required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (fallback), `DATABASE_URL`, `REDIS_URL`, `VECTOR_STORE_TYPE`
- [x] Install shared tooling versions: Python 3.11+, Node 20+, PostgreSQL with pgvector
- [x] Agree on branch strategy (e.g., `main` protected, feature branches + PR review by one other teammate)

**Exit criteria:** Every team member can clone the repo, set up Python venv, install npm packages, and verify health checks locally without Docker errors. (Completed)

---

## Phase 1 — Project Setup & Scaffolding

**Goal:** Empty but runnable skeleton for backend and frontend, wired together.

### 1.1 Repository Structure
- [x] Create folder structure exactly as defined in `AGENTS.md` (`/backend`, `/frontend`, `/docs`, `/scripts`)
- [x] Add `docker-compose.yml` (optional for containerized deployments/staging parity)

### 1.2 Backend Scaffold
- [x] Initialize FastAPI app (`backend/api/main.py`) with a health-check route (`GET /health`)
- [x] Set up `requirements.txt` (fastapi, uvicorn, sqlalchemy, asyncpg, psycopg2-binary, alembic, celery, redis, pgvector, sentence-transformers, anthropic, rank-bm25, pytest, black, ruff)
- [x] Configure `ruff` + `black` + pre-commit hook

### 1.3 Frontend Scaffold
- [x] Initialize React + TypeScript app via Vite in `/frontend`
- [x] Install Tailwind CSS, configure `tailwind.config.js`
- [x] Confirm `npm run dev` renders a placeholder "EduSync" page

### 1.4 CI Setup
- [x] GitHub Actions workflow: run backend `pytest` + `ruff` and frontend `npm test` + `npm run lint` on every PR

**Exit criteria:** `uvicorn api.main:app --reload` starts FastAPI (`/health` returns 200) and `npm run dev` starts React dev server natively; CI green on an empty-but-structured repo. (Completed)

---

## Phase 2 — Database Design & Setup

**Goal:** Schema in place, migrations working, before any ingestion or retrieval code depends on it.

### 2.1 Database & pgvector Setup
- [x] Configure PostgreSQL with `pgvector` extension (`CREATE EXTENSION IF NOT EXISTS vector;`)
- [x] Configure SQLAlchemy async engine (`postgresql+asyncpg://...`)
- [x] Set up Alembic (`alembic init migrations`) with pgvector type support

### 2.2 Core Tables (per TDD §4)
- [x] Migration 1: `documents` table (source_url, source_type, department, owner, content_hash, status, timestamps)
- [x] Migration 2: `chunks` table (document_id FK, content, token_count, embedding VECTOR(384), last_verified) + `ivfflat` / `hnsw` index
- [x] Migration 3: `conflicts` table (document_ids[], detected_at, resolved_by, resolved_at, resolution_note)
- [x] Migration 4: `queries_log` table (question, retrieved_chunk_ids[], answer, confidence_score, feedback, created_at)

### 2.3 SQLAlchemy Models & Seed Data
- [x] Write ORM models mirroring the DDL exactly (`backend/models/`) using PostgreSQL + pgvector column types
- [x] Write a seed script (`scripts/seed_dev_data.py`) with 3–5 sample documents (a fake exam circular, fee notice, syllabus PDF) for local development without needing real college data yet

**Exit criteria:** `alembic upgrade head` runs clean on a fresh PostgreSQL database with pgvector; seed script populates sample rows visible via DB client; a basic query from each table returns expected columns. (Completed)

---

## Phase 3 — Backend: Ingestion Pipeline

**Goal:** Documents go in, get chunked, embedded, and stored — self-updating from day one, not bolted on later.

### 3.1 Fetchers
- [x] `fetch_pdf(url)` — download + extract text (PyMuPDF or pdfplumber)
- [x] `fetch_pdf` Page-Level Hybrid OCR — automatically routes low text density (<40 chars) or large raster images (>300x200 px) to Baidu PaddleOCR-VL
- [x] Early SHA-256 binary content hash check — sub-millisecond bypass of PDF parsing and OCR for unchanged documents
- [x] Clean portal metadata extraction (`title`, `sno`, `date`, `portal_id`, `department`) directly from college website API/HTML
- [x] `fetch_html(url)` — fetch + strip boilerplate (readability/BeautifulSoup)
- [x] `fetch_sheet(url_or_path)` — parse CSV/Sheets export into structured rows

### 3.2 Change Detection (per TDD §5.1)
- [x] Implement `normalize_content()` (strip whitespace/boilerplate before hashing)
- [x] Implement `compute_hash()` (SHA-256)
- [x] Implement comparison against stored `documents.content_hash`; mark `pending` on mismatch
- [x] Corrigendum & revision detection — auto-supersedes older notices in same department on topic match

### 3.3 Chunking (per TDD §5.2)
- [x] Implement semantic-boundary chunker (headings/paragraphs first, 300–500 tokens, ~15% overlap)
- [x] Table row splitting preserving repeated Markdown table column headers (`| Col 1 | Col 2 |\n|---|---|`)
- [x] Regex boilerplate stripping (letterheads, distribution lists "Copy to:...", page footers)
- [x] Contextual header injection (`[Notice: ... | Ref: ... | Date: ... | Dept: ...]`) with strict token budget ($\le 550$ tokens)
- [x] Short notice preservation (no arbitrary force-splitting of single-window circulars)
- [x] Attach parent metadata (department, owner, source_url, original_content) to every chunk

### 3.4 Embedding & Upsert
- [x] Wire in BAAI/bge-m3 (1024-d) locally and Jina Embeddings v3 for cloud acceleration
- [x] Write `upsert_chunks()` — insert new/changed chunks into Postgres + vector index, update `last_verified`
- [x] Native document metadata persistence (`title`, `notice_sno`, `notice_date`, `portal_id`)
- [x] Deterministic portal chronological ordering index (`idx_documents_portal_order`)

### 3.5 Conflict Detection (per TDD §5.4)
- [x] Implement rule-based same-department/same-type overlap check
- [x] On conflict: create `conflicts` row, set both documents' status to `conflicted`, exclude from retrieval

### 3.6 Scheduling
- [x] Set up Celery worker + Celery Beat (default interval: every 6 hours, configurable)
- [x] Add manual trigger task (used by the admin "re-ingest" and live pipeline inspector)

### 3.7 Static College Knowledge Base
- [x] Create curated static Markdown documents in `backend/data/static/` (About College, Academic Regulations, Departments/HODs, Fee Structure, Hostels & Facilities, Helplines)
- [x] Implement `scripts/ingest_static_data.py` to chunk, hash-check, and embed static documents into PostgreSQL pgvector

**Exit criteria:** Running the ingestion task against seeded and real scanned documents produces complete multi-page chunks with tables; re-running with an unchanged source produces zero new embeddings; static institutional documents are fully queryable. (Completed)

---

## Phase 4 — Backend: Retrieval & Generation API

**Goal:** A working `/chat` endpoint with hybrid search, reranking, confidence gating, and citations.

### 4.1 Hybrid Search
- [x] Implement BM25/keyword search with stored `to_tsvector('simple', content)` and GIN trigram index
- [x] Implement vector ANN search against `chunks.embedding` (1024-dim HNSW)
- [x] Candidate pool scaling (`candidate_k = 40`, `top_k = 25`) preventing large-corpus truncation
- [x] Soft department RRF multiplier (1.3x) and recency decay boosting (180-day half-life)
- [x] Contextual query rewriting cascade (`gemini-3.5-flash-lite` -> `gemini-3.8-flash` -> `gemini-3.5-flash`) for multi-turn chats

### 4.2 Reranking
- [x] Integrate cross-encoder reranker (`ms-marco-MiniLM` locally, or Jina Reranker v2 API)
- [x] Feed clean natural student query directly to cross-encoder

### 4.3 Confidence Gate & Fallback
- [x] Three-tier calibrated confidence gate:
  - $\ge 0.75$: Direct answer with source citations
  - $0.40 - 0.75$: Answer with student caveat banner
  - $< 0.40$: Official fallback response (zero hallucination)
- [x] Single-call Gemini structured JSON evidence verification achieving 100.00% abstention accuracy on unanswerables

### 4.4 LLM Generation & Citations
- [x] Build grounded-generation prompt (expanded to 16,000 characters context)
- [x] Call Gemini Flash API with OpenAI fallback
- [x] Attach `sources[]` (`document`, `last_verified`, `url`) to the response

### 4.5 API Endpoints
- [x] `POST /chat` (supports query, conversation history, and department intent)
- [x] `GET /admin/sources` & `POST /admin/sources` (priority management, limits)
- [x] `GET /admin/sources/{id}/documents` (exact chronological portal order)
- [x] `GET /admin/sources/{id}/live-feed` (ECA portal live proxy)
- [x] `GET /admin/sources/live-progress` (real-time step execution tracker)
- [x] `GET /admin/departments`
- [x] `GET /admin/jina-usage` (token quota monitor)
- [x] `GET /health`

### 4.6 Tests
- [x] 117 automated unit and contract tests in `backend/tests/` passing cleanly
- [x] 63-query evaluation benchmark harness (`eval/eval_set.json` & `eval/run_eval.py`):
  - Recall@5: 100.00%
  - Recall@10: 100.00%
  - MRR: 0.9464
  - Abstention Accuracy: 100.00%
  - End-to-End Correctness: 74.60%

**Exit criteria:** Hitting `/chat` with a seeded-data question returns a correct, cited answer; an out-of-scope question returns the fallback message, not a guess; all contract tests pass.

---

## Phase 5 — Frontend: Student Chat UI

**Goal:** A student can ask a question and see a trustworthy, cited answer.

- [x] `ChatWindow` component: message list + input box
- [x] `MessageBubble` component: renders answer text, source citation(s), `last_verified` date, confidence indicator (High/Medium/Low)
- [x] API wrapper (`/src/api/chat.ts`) calling `POST /chat`
- [ ] Department Selector filter (All, CSE, Examination, Registrar, Civil, EE, Mech, ECE, MCA, MBA) passed to chat API
- [ ] Feedback control (thumbs up/down) wired to `POST /feedback`
- [ ] Loading/error states (API timeout, fallback response styling distinct from normal answers)
- [x] Basic responsive layout (mobile + desktop)

**Exit criteria:** End-to-end manual test — type a question in the browser, see a real answer with citation sourced from the seeded documents.

---

## Phase 6 — Frontend: Admin Dashboard

**Goal:** Content owners can see system health and resolve conflicts without touching the DB directly.

- [ ] `DocumentsTable` — list with status badges (fresh/stale/conflicted/pending), manual "Re-ingest" button per row
- [ ] `ConflictsPanel` — list unresolved conflicts, action to mark one document authoritative
- [ ] `AnalyticsPanel` — query volume chart, top unanswered questions, feedback breakdown
- [ ] Basic auth gate (even simple shared-password auth is acceptable for MVP; note as a known limitation)

**Exit criteria:** Editing a seeded source and re-running ingestion is visible as a status change in the dashboard within one refresh; a manually created conflict can be resolved through the UI and disappears from retrieval exclusion.

---

## Phase 7 — Integration Testing & Sem 7 Submission Prep

- [x] Full end-to-end test: add a new document → auto-detected on next scheduled run → answer reflects it within the interval → citation and freshness date correct
- [x] Run comprehensive database audit: 100% metadata completeness, 0 orphan records, verified vector integrity
- [x] Backfill legacy documents (`owner`, `original_content`, `notice_memory` fields)
- [x] Implement Query Lifecycle Logging (`queries_log`) and student feedback API (`POST /chat/feedback`)
- [x] Automated conflict resolution script with audit logging (`scripts/resolve_pending_conflicts.py`)
- [ ] Run the 100-question evaluation harness, record baseline precision/accuracy numbers
- [ ] Fix highest-impact failures surfaced by the harness
- [ ] Record demo video / prepare live demo script
- [ ] Write Sem 7 interim report referencing PRD milestones M1–M4 as completed

**Exit criteria:** All Sem 7 milestones (per PRD §8) demonstrably complete; evaluation numbers documented for comparison in Sem 8's ablation study.

---

## Phase 8 — Sem 8: Scale, Evaluate, Deploy (Forward-Looking Outline)

*(Detailed task breakdown to follow once Sem 7 is complete — outlined here so the team can see the full arc.)*

- [ ] Harden ingestion against messier real-world documents (scanned PDFs, inconsistent table formats)
- [ ] Build the static-vs-self-updating ablation harness (per TDD §9) and produce the comparison report
- [ ] Deploy to a persistent environment (VM/Render) for real student usage
- [ ] Collect real usage logs, iterate on confidence threshold and fallback wording
- [ ] Draft paper/report for publication, prepare final submission materials

---

## Dependency Summary (why this order)

```
Phase 0 (setup) → Phase 1 (scaffold) → Phase 2 (database)
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                       ▼
                Phase 3 (ingestion)                     Phase 4 depends on
                          │                              Phase 2 schema +
                          ▼                              Phase 3 populated data
                Phase 4 (retrieval/API)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
     Phase 5 (student UI)   Phase 6 (admin dashboard)
              │                       │
              └───────────┬───────────┘
                          ▼
              Phase 7 (integration & submission)
                          │
                          ▼
              Phase 8 (Sem 8 scale/publish)
```
