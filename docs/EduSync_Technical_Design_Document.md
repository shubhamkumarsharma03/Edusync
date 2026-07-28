# Technical Design Document (TDD)
## EduSync — Self-Updating Retrieval-Augmented Knowledge Base Chatbot

**Version:** 1.0
**Status:** Draft
**Related Docs:** `EduSync_PRD.md`, Project Synopsis (`Project_Synopsis.docx`)
**Last Updated:** July 25, 2026

---

## 1. Purpose & Scope

This document translates the PRD's functional requirements into concrete technical decisions: architecture, data schemas, algorithms, APIs, and deployment design. It is the implementation reference for the 4-person team; the PRD stays the source of truth for *what* and *why*, this document is the *how*.

---

## 2. Tech Stack Decisions

| Layer | Choice | Rationale |
|---|---|---|
| Backend API | Python + FastAPI | Async support, native fit with ML/embedding libraries, auto-generated OpenAPI docs |
| Ingestion Workers | Python (APScheduler / Celery + Redis) | Same language as backend; Celery gives retry/backoff for free |
| Embeddings | Sentence-Transformers (`all-MiniLM-L6-v2` for dev) → OpenAI/Voyage embeddings for prod-quality | Free/local for development iteration; swap to hosted model once pipeline is stable |
| Vector Store | ChromaDB (dev) → pgvector (prod) | Chroma is zero-config for local dev; pgvector lets us keep metadata + vectors in one Postgres instance for production, simplifying conflict/freshness queries |
| Relational Store | PostgreSQL | Stores documents, chunks metadata, conflicts, query logs — needed for joins Chroma alone can't do |
| LLM (generation) | Claude API (primary), OpenAI as fallback | Strong grounded-answer + citation behavior; fallback avoids single-vendor outage risk |
| Reranker | Cross-encoder (`ms-marco-MiniLM`) or Cohere Rerank API | Reduces false positives from pure vector similarity before hitting the LLM |
| Frontend | React + TypeScript + Tailwind CSS | Matches team's existing skillset (per portfolio work); fast to iterate |
| Deployment | Docker Compose (dev) → single VM or Render (prod) | No need for k8s at this scale; keep ops overhead low for a student team |
| Task/Job Queue | Redis + Celery beat | Handles the scheduled re-ingestion job (FR-4) reliably with retries |

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                              │
│  College website | PDF circulars | Sheets/CSV exports              │
└───────────────────────────────┬─────────────────────────────────┘
                                │  (polled every N hours)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INGESTION SERVICE (Celery worker)              │
│  1. Fetch source → 2. Compute SHA-256 hash → 3. Compare to DB      │
│  4. If changed: parse → chunk → tag metadata → embed → upsert     │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     STORAGE LAYER                                  │
│  PostgreSQL (documents, chunks metadata, conflicts, logs)          │
│  Vector Store (chunk embeddings, ANN index)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RETRIEVAL & GENERATION API (FastAPI)             │
│  /chat →  hybrid search → rerank → confidence gate → LLM call     │
│         → citation attach → response                              │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
┌───────────────────────────┐      ┌───────────────────────────────┐
│   STUDENT CHAT UI (React)  │      │   ADMIN DASHBOARD (React)       │
│   Ask, view answer+source  │      │   Source status, conflicts,     │
│                            │      │   manual re-ingest, analytics   │
└───────────────────────────┘      └───────────────────────────────┘
```

---

## 4. Database Schema (PostgreSQL DDL)

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url      TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('pdf', 'html', 'sheet')),
    department      TEXT,
    owner           TEXT,
    content_hash    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'fresh'
                        CHECK (status IN ('fresh', 'stale', 'conflicted', 'pending')),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    token_count     INT NOT NULL,
    embedding       VECTOR(384),           -- pgvector column; dim depends on embedding model
    last_verified   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE conflicts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_ids    UUID[] NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    resolution_note TEXT
);

CREATE TABLE queries_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question            TEXT NOT NULL,
    retrieved_chunk_ids UUID[],
    answer              TEXT,
    confidence_score    NUMERIC(4,3),
    feedback            TEXT CHECK (feedback IN ('up', 'down') OR feedback IS NULL),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 5. Core Algorithms

### 5.1 Change Detection (Hash Diff)
```
for each registered source:
    fetch raw content
    new_hash = SHA256(normalized_content)
    if new_hash != documents.content_hash:
        mark document status = 'pending'
        enqueue re-ingestion task
    else:
        update last_checked_at
```
`normalized_content` strips whitespace/HTML boilerplate so trivial formatting changes don't trigger unnecessary re-embeds.

### 5.2 Chunking Strategy
- Split by semantic boundaries first (headings, paragraphs), not fixed character count.
- Target 300–500 tokens per chunk with ~15% overlap between adjacent chunks to preserve context across boundaries.
- Tables are kept intact as a single chunk regardless of size (never split mid-row).
- Each chunk inherits parent document metadata (`department`, `owner`, `source_url`).

### 5.3 Hybrid Retrieval + Reranking
```
1. keyword_results = BM25_search(query, top_k=20)
2. vector_results = ANN_search(embed(query), top_k=20)
3. merged = dedupe(keyword_results + vector_results)
4. reranked = cross_encoder_score(query, merged)   # sort by relevance
5. top_chunks = reranked[:5]
6. if top_chunks[0].score < CONFIDENCE_THRESHOLD:
       return fallback_response()
7. else:
       return generate_answer(query, top_chunks)
```
`CONFIDENCE_THRESHOLD` is tuned empirically against the 100-question test set (start at 0.55 on a 0–1 normalized reranker score, adjust based on false-negative rate).

### 5.4 Conflict Detection
When two active documents are tagged with overlapping `department` + a matching document "type" heuristic (e.g., both classified as "exam schedule" via a lightweight classifier or filename/keyword rule) and their content disagrees on a extracted key fact (date, amount), flag a `conflicts` row instead of silently ingesting both as retrievable.

---

## 6. API Design (FastAPI)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | `{ "question": str }` → `{ answer, sources[], confidence }` |
| `POST` | `/feedback` | `{ query_id, feedback: "up"/"down" }` |
| `GET` | `/admin/documents` | List all documents with status |
| `POST` | `/admin/documents/{id}/reingest` | Force re-ingestion of one source |
| `GET` | `/admin/conflicts` | List unresolved conflicts |
| `POST` | `/admin/conflicts/{id}/resolve` | `{ authoritative_document_id, note }` |
| `GET` | `/admin/analytics` | Query volume, top unanswered questions, feedback breakdown |

Example response from `/chat`:
```json
{
  "answer": "The mid-semester exams begin on 14 September 2026.",
  "sources": [
    {
      "document": "Mid-Sem Exam Schedule Circular",
      "last_verified": "2026-07-20T10:00:00Z",
      "url": "https://college.edu/circulars/exam-sched.pdf"
    }
  ],
  "confidence": 0.82
}
```

---

## 7. Sequence: Self-Updating Flow

```
Celery Beat (every 6h)
     │
     ▼
Ingestion Worker: fetch source → hash compare
     │
     ├── unchanged → update last_checked_at, exit
     │
     └── changed
           │
           ▼
     Parse & chunk → tag metadata → embed changed chunks
           │
           ▼
     Upsert into vector store + Postgres (chunks, documents)
           │
           ▼
     Run conflict check against same-department/type docs
           │
           ├── conflict found → create `conflicts` row, status='conflicted'
           │
           └── no conflict → status='fresh', last_verified=now()
```

---

## 8. Error Handling & Resilience

| Failure Mode | Handling |
|---|---|
| Source fetch fails (timeout, 404) | Retry 3x with exponential backoff (Celery); log failure; keep last-known-good chunks live |
| Embedding API rate-limited | Queue and retry; batch embed requests where possible |
| LLM API outage (primary) | Fall back to secondary provider; if both fail, return a static "service temporarily unavailable" message, never a hallucinated guess |
| Conflicting sources not yet resolved | Exclude both from retrieval until admin resolves, rather than guessing which is correct |
| Malformed/corrupt PDF | Log and skip; flag in admin dashboard for manual review |

---

## 9. Testing Strategy

- **Unit tests:** chunking boundaries, hash-diff logic, conflict-detection heuristic.
- **Integration tests:** full ingestion → retrieval → generation flow against a fixture set of sample documents.
- **Evaluation harness (offline):** run the 100-question test set nightly in CI; track precision@5, answer accuracy, and confidence-threshold calibration over time.
- **Ablation testing:** identical test set run against a "static" build (self-update disabled) to produce the Sem 8 comparison report.
- **Manual QA:** weekly team review of real chat logs for hallucination/fallback correctness.

---

## 10. Deployment Design

- **Dev:** Docker Compose spinning up FastAPI, Postgres+pgvector, Redis, and the React dev server.
- **Prod:** Single VM (or Render/Railway) running Dockerized services; Postgres managed instance if budget allows, otherwise same VM.
- **CI/CD:** GitHub Actions — run tests on PR, build Docker images on merge to `main`, manual deploy trigger for the demo environment.
- **Secrets:** LLM/embedding API keys stored in environment variables / GitHub Actions secrets, never committed.

---

## 11. Open Technical Decisions

- Exact reranker choice (self-hosted cross-encoder vs. Cohere Rerank API) — depends on latency budget once end-to-end timing is measured.
- Whether conflict-type classification (Section 5.4) is a rule-based heuristic or a small trained classifier — start rule-based, revisit if false-positive rate is high.
- Embedding dimensionality and cost tradeoff for the pgvector column once the production embedding model is finalized.
