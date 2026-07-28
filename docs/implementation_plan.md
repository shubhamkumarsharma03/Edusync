# The Blueprint — Implementation Plan
## EduSync: Step-by-Step Technical Build Plan

**Version:** 1.0
**Companion docs:** `EduSync_PRD.md`, `EduSync_Technical_Design_Document.md`, `AGENTS.md`
**Last Updated:** July 25, 2026

This plan sequences the build so nothing later depends on something not yet built — project scaffolding first, then the database (everything else reads/writes to it), then backend services (ingestion → retrieval → API), then frontend. Each phase lists concrete tasks, exit criteria, and which FR/milestone from the PRD it satisfies.

---

## Phase 0 — Prerequisites & Team Setup

**Goal:** Everyone can run the project locally before any feature code is written.

- [ ] Create GitHub repo, add `AGENTS.md`, `docs/` folder with PRD + TDD copied in
- [ ] Assign the 4 roles (per TDD/PRD): Ingestion owner, Retrieval/Vector DB owner, Backend API/Evaluation owner, Frontend/UX owner
- [ ] Set up `.env.example` listing required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (fallback), `DATABASE_URL`, `REDIS_URL`
- [ ] Install shared tooling versions: Python 3.11+, Node 20+, Docker, Docker Compose
- [ ] Agree on branch strategy (e.g., `main` protected, feature branches + PR review by one other teammate)

**Exit criteria:** Every team member can clone the repo and run `docker compose up` without errors (even with empty services).

---

## Phase 1 — Project Setup & Scaffolding

**Goal:** Empty but runnable skeleton for backend and frontend, wired together.

### 1.1 Repository Structure
- [ ] Create folder structure exactly as defined in `AGENTS.md` (`/backend`, `/frontend`, `/docs`, `/scripts`)
- [ ] Add `docker-compose.yml` with services: `api`, `postgres`, `redis`, `frontend` (dev server)

### 1.2 Backend Scaffold
- [ ] Initialize FastAPI app (`backend/api/main.py`) with a health-check route (`GET /health`)
- [ ] Set up `requirements.txt` (fastapi, uvicorn, sqlalchemy, alembic, celery, redis, pgvector, sentence-transformers, anthropic, pytest, black, ruff)
- [ ] Configure `ruff` + `black` + pre-commit hook

### 1.3 Frontend Scaffold
- [ ] Initialize React + TypeScript app via Vite in `/frontend`
- [ ] Install Tailwind CSS, configure `tailwind.config.js`
- [ ] Confirm `npm run dev` renders a placeholder "EduSync" page

### 1.4 CI Setup
- [ ] GitHub Actions workflow: run backend `pytest` + `ruff` and frontend `npm test` + `npm run lint` on every PR

**Exit criteria:** `docker compose up --build` starts Postgres, Redis, FastAPI (`/health` returns 200), and the React dev server, with CI green on an empty-but-structured repo.

---

## Phase 2 — Database Design & Setup

**Goal:** Schema in place, migrations working, before any ingestion or retrieval code depends on it.

### 2.1 Postgres + pgvector
- [ ] Add `pgvector` extension to the Postgres Docker image (`CREATE EXTENSION IF NOT EXISTS vector;`)
- [ ] Set up Alembic (`alembic init migrations`)

### 2.2 Core Tables (per TDD §4)
- [ ] Migration 1: `documents` table (source_url, source_type, department, owner, content_hash, status, timestamps)
- [ ] Migration 2: `chunks` table (document_id FK, content, token_count, embedding VECTOR, last_verified) + `ivfflat` index
- [ ] Migration 3: `conflicts` table (document_ids[], detected_at, resolved_by, resolved_at, resolution_note)
- [ ] Migration 4: `queries_log` table (question, retrieved_chunk_ids[], answer, confidence_score, feedback, created_at)

### 2.3 SQLAlchemy Models & Seed Data
- [ ] Write ORM models mirroring the DDL exactly (`backend/models/`)
- [ ] Write a seed script (`scripts/seed_dev_data.py`) with 3–5 sample documents (a fake exam circular, fee notice, syllabus PDF) for local development without needing real college data yet

**Exit criteria:** `alembic upgrade head` runs clean on a fresh DB; seed script populates sample rows visible via `psql` or a DB GUI; a basic `SELECT` from each table returns expected columns.

---

## Phase 3 — Backend: Ingestion Pipeline

**Goal:** Documents go in, get chunked, embedded, and stored — self-updating from day one, not bolted on later.

### 3.1 Fetchers
- [ ] `fetch_pdf(url)` — download + extract text (PyMuPDF or pdfplumber)
- [ ] `fetch_html(url)` — fetch + strip boilerplate (readability/BeautifulSoup)
- [ ] `fetch_sheet(url_or_path)` — parse CSV/Sheets export into structured rows

### 3.2 Change Detection (per TDD §5.1)
- [ ] Implement `normalize_content()` (strip whitespace/boilerplate before hashing)
- [ ] Implement `compute_hash()` (SHA-256)
- [ ] Implement comparison against stored `documents.content_hash`; mark `pending` on mismatch

### 3.3 Chunking (per TDD §5.2)
- [ ] Implement semantic-boundary chunker (headings/paragraphs first, 300–500 tokens, ~15% overlap)
- [ ] Special-case: keep tables as single chunks
- [ ] Attach parent metadata (department, owner, source_url) to every chunk

### 3.4 Embedding & Upsert
- [ ] Wire in Sentence-Transformers (`all-MiniLM-L6-v2`) for local dev
- [ ] Write `upsert_chunks()` — insert new/changed chunks into Postgres + vector index, update `last_verified`

### 3.5 Conflict Detection (per TDD §5.4)
- [ ] Implement rule-based same-department/same-type overlap check
- [ ] On conflict: create `conflicts` row, set both documents' status to `conflicted`, exclude from retrieval

### 3.6 Scheduling
- [ ] Set up Celery worker + Celery Beat (default interval: every 6 hours, configurable)
- [ ] Add manual trigger task (used later by the admin "re-ingest" button)

**Exit criteria:** Running the ingestion task against the seeded sample documents produces correct rows in `documents`/`chunks`; re-running with an unchanged source produces zero new embeddings; editing a seed doc and re-running produces exactly the changed chunks.

---

## Phase 4 — Backend: Retrieval & Generation API

**Goal:** A working `/chat` endpoint with hybrid search, reranking, confidence gating, and citations.

### 4.1 Hybrid Search
- [ ] Implement BM25/keyword search (e.g., Postgres full-text search or `rank_bm25`)
- [ ] Implement vector ANN search against `chunks.embedding`
- [ ] Merge + deduplicate results

### 4.2 Reranking
- [ ] Integrate cross-encoder reranker (`ms-marco-MiniLM` locally, or Cohere Rerank API)
- [ ] Sort merged candidates by rerank score

### 4.3 Confidence Gate & Fallback
- [ ] Define `CONFIDENCE_THRESHOLD` as a configurable constant
- [ ] If top score < threshold → return fallback response (per PRD FR-15) instead of calling the LLM

### 4.4 LLM Generation & Citations
- [ ] Build the grounded-generation prompt (answer only from provided chunks, cite source)
- [ ] Call Claude API (primary) with OpenAI fallback on failure
- [ ] Attach `sources[]` (document name, `last_verified`, `url`) to the response

### 4.5 API Endpoints (per TDD §6)
- [ ] `POST /chat`
- [ ] `POST /feedback`
- [ ] `GET /admin/documents`
- [ ] `POST /admin/documents/{id}/reingest`
- [ ] `GET /admin/conflicts`
- [ ] `POST /admin/conflicts/{id}/resolve`
- [ ] `GET /admin/analytics`

### 4.6 Tests
- [ ] Contract tests for every endpoint (FastAPI `TestClient`)
- [ ] Retrieval tests against the fixture question set (`backend/tests/fixtures/eval_questions.json`)

**Exit criteria:** Hitting `/chat` with a seeded-data question returns a correct, cited answer; an out-of-scope question returns the fallback message, not a guess; all contract tests pass.

---

## Phase 5 — Frontend: Student Chat UI

**Goal:** A student can ask a question and see a trustworthy, cited answer.

- [ ] `ChatWindow` component: message list + input box
- [ ] `MessageBubble` component: renders answer text, source citation(s), `last_verified` date, confidence indicator (High/Medium/Low)
- [ ] API wrapper (`/src/api/chat.ts`) calling `POST /chat`
- [ ] Feedback control (thumbs up/down) wired to `POST /feedback`
- [ ] Loading/error states (API timeout, fallback response styling distinct from normal answers)
- [ ] Basic responsive layout (mobile + desktop)

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

- [ ] Full end-to-end test: add a new document → auto-detected on next scheduled run → answer reflects it within the interval → citation and freshness date correct
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
