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
| Backend API | Python 3.11+ + FastAPI | Async support, native fit with ML/embedding libraries, auto-generated OpenAPI docs |
| Ingestion Workers | Python (Async in-process for dev; Celery + Redis for prod) | In-process execution for zero-Docker local development; Celery + Redis for production with retry/backoff |
| Document OCR | Baidu PaddleOCR-VL + Persistent SHA-256 Cache | Direct Markdown output with native tables, heading hierarchy, and zero redundant OCR via `.cache/ocr_markdown/` |
| Document Web Reader | Jina Reader API (`https://r.jina.ai/`) + Playwright | Direct URL-to-markdown extraction without browser rendering overhead, plus Playwright for dynamic SPA pages |
| Embeddings | Jina Embeddings v3 (`1024` dimensions, task-specific adapters) / BAAI/bge-m3 | Cloud-accelerated Jina v3 (`retrieval.passage` / `retrieval.query`) with local `bge-m3` fallback on exact 1024-d schema parity |
| Vector Store | pgvector (PostgreSQL extension, HNSW cosine index) | Unified storage for relational metadata and 1024-dim dense embeddings (`m=16, ef_construction=64`) |
| Relational Store | PostgreSQL 16+ | Stores documents, departments, ingestion sources, chunks, conflicts, and query logs with full type-safety |
| LLM (generation) | Gemini Flash (`google-genai`), OpenAI/Claude fallback | High-speed grounded answer generation with native table rendering and source citations |
| Reranker | Jina Reranker v2 (`jina-reranker-v2-base-multilingual`) / `ms-marco-MiniLM-L-6-v2` | Multilingual cross-encoder API reranking candidate pool from 20 to top 5, with local CPU CrossEncoder fallback |
| Quota Monitoring | `JinaTokenTracker` + `/admin/jina-usage` | Real-time thread-safe tracking across embeddings & reranking against Jina's 10,000,000 free-tier limit |
| Frontend | React 18 + TypeScript + Tailwind CSS | Minimal, accessible UI with Lucide icons (zero emojis), live pipeline inspector with 5s auto-polling |
| Deployment | Native Local Dev (Python venv + Node) / Docker Compose | Fast local development without Docker; containerized deployments for cloud and staging parity |

---

## 3. High-Level Architecture

```mermaid
flowchart TD
    subgraph DataSources ["1. Data Sources & Ingestion"]
        DS1["ecajmer.ac.in Institutional Portals"] --> CRAWL["Playwright Portal Crawler / Jina Reader"]
        CRAWL --> HASH["SHA-256 Content Hash Diff"]
        HASH -- "Hash Match (Unchanged)" --> SKIP["Update last_checked_at (0 Compute Cost)"]
        HASH -- "New or Modified" --> OCR["Baidu PaddleOCR-VL Engine"]
        OCR <--> OCACHE[("Persistent SHA-256 Markdown Cache")]
    end

    subgraph ChunkingAndEmbedding ["2. Structure-Aware Chunking & Embedding"]
        OCR --> MD["Structured Markdown with Headings & Tables"]
        MD --> CHUNKER["SemanticChunker with Breadcrumb Hierarchy"]
        CHUNKER --> ENT["Entity Extraction (semester, notice_sno, academic_year)"]
        CHUNKER --> BC["Inject Context Breadcrumbs: [Context: # > ## > ###]"]
        BC & ENT --> EMBED{"Provider Route"}
        EMBED -- "Jina Available" --> JINA_EMBED["Jina Embeddings v3 API (1024-d)<br/>task: 'retrieval.passage' (Batch: 32)"]
        EMBED -- "Local Fallback" --> LOCAL_EMBED["BAAI/bge-m3 Local Model (1024-d)"]
        JINA_EMBED & LOCAL_EMBED --> UP["Upsert Chunks & Document Metadata"]
    end

    subgraph StorageLayer ["3. Storage Layer (PostgreSQL 16+ with pgvector)"]
        UP --> DB_DOCS[("documents & departments")]
        UP --> DB_CHUNKS[("chunks (vector(1024), HNSW Index)")]
        UP --> DB_CONF[("conflicts & queries_log")]
    end

    subgraph RetrievalPipeline ["4. Intent-Routed Hybrid Retrieval"]
        QUERY["Student Query (e.g., 'cse 3rd sem tt')"] --> NORM["CollegeQueryNormalizer"]
        NORM --> DETECT["Entity Intent: Dept ('CSE'), Sem ('3rd Sem'), Type ('timetable')"]
        DETECT --> ROUTE{"Department Intent Detected?"}
        ROUTE -- Yes --> SEARCH_FILT["Filtered Search: Vector (task='retrieval.query') + Keyword (FTS)"]
        ROUTE -- No --> SEARCH_UNFILT["Unconstrained Hybrid Search (Vector + Keyword)"]
        SEARCH_FILT -- "0 Results" --> SEARCH_UNFILT
        SEARCH_FILT & SEARCH_UNFILT --> RRF["Reciprocal Rank Fusion (RRF k=60)<br/>Top 20 Candidate Pool"]
        RRF --> RERANK{"Reranker Route"}
        RERANK -- "Jina Available" --> JINA_RERANK["Jina Reranker v2 API<br/>jina-reranker-v2-base-multilingual<br/>Top 5 Chunks"]
        RERANK -- "Local Fallback" --> LOCAL_RERANK["CrossEncoder (ms-marco-MiniLM-L-6-v2)<br/>Top 5 Chunks"]
        JINA_RERANK & LOCAL_RERANK --> GATE{"Top Score >= CONFIDENCE_THRESHOLD (0.55)?"}
        GATE -- No --> FALLBACK["Safe Fallback Response (Zero Hallucination)"]
        GATE -- Yes --> LLM["LLM Synthesis (Gemini Flash) with Citations & Tables"]
    end

    subgraph TokenTracking ["5. Quota & Operations Management"]
        JINA_EMBED -.-> TRACKER[("JinaTokenTracker<br/>10,000,000 Free Quota")]
        JINA_RERANK -.-> TRACKER
        TRACKER -.-> ADMIN_API["GET /admin/jina-usage"]
    end

    subgraph PresentationLayer ["6. Presentation Layer"]
        LLM & FALLBACK --> CHAT_UI["Student Chat Interface"]
        DB_DOCS & DB_CHUNKS & ADMIN_API --> ADMIN_UI["Admin Dashboard & Live Pipeline Inspector"]
    end
```

---

## 4. Database Schema (PostgreSQL DDL)

```sql
CREATE TABLE departments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    code        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingestion_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id   UUID REFERENCES departments(id) ON DELETE SET NULL,
    portal_url      TEXT NOT NULL UNIQUE,
    priority        INT NOT NULL DEFAULT 5,
    max_pages       INT NOT NULL DEFAULT 3,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    last_scraped_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
    embedding       VECTOR(1024),          -- 1024-dim BAAI/bge-m3 embedding
    last_verified   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX chunks_embedding_idx ON chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

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

### 5.1 Change Detection (Hash Diff & Persistent OCR Cache)
```
for each registered source in ingestion_sources:
    fetch raw document content (PDF/HTML)
    new_hash = SHA256(raw_content)
    if new_hash != documents.content_hash:
        check local persistent OCR cache (.cache/ocr_markdown/{hash}.md)
        if cached:
            markdown = read_cache()
        else:
            markdown = baidu_paddleocr_vl(raw_content)
            save_cache(new_hash, markdown)
        chunk, embed with BGE-M3, and upsert
    else:
        update documents.last_checked_at (0 compute and 0 embedding cost)
```

### 5.2 Structure-Aware Markdown Chunking & Breadcrumbs
- **Heading Stack Hierarchy**: Baidu OCR output is parsed into Markdown sections while maintaining a heading stack (`# > ## > ### > ####`).
- **Context Injection**: Each child paragraph and table chunk is prepended with `[Context: Breadcrumb Path]\n\n`, allowing dense vectors and keyword FTS to match hierarchical section context.
- **Entity Extraction**: Regex extractors pull key metadata fields:
  - `semester`: e.g. `3rd Sem`, `1st Sem`
  - `notice_sno`: Official dispatch code (e.g. `ECA/Acad/2026/1042`, `F.(2)/Admin/Estt/2025/89`)
  - `academic_year`: e.g. `2025-26`, `2026-2027`
- **Atomic Tables**: Markdown tables are kept intact as dedicated chunks with natural language row statements and breadcrumb headers.
- **Target Size**: 800 tokens target (up to 1,200 max) to fully exploit BGE-M3's 8,192 token window.

### 5.3 Intent-Routed Hybrid Retrieval & Reranking
```
1. norm = CollegeQueryNormalizer.normalize(query)
   -> extracts detected_departments, detected_semesters, expanded_vector, expanded_keyword
2. query_vec = Embedder.aembed_texts([norm.expanded_vector], task="retrieval.query")
3. if norm.detected_departments:
       vector_results = ANN_search(query_vec, filter=departments, top_k=20)
       keyword_results = FTS_search(norm.expanded_keyword, filter=departments, top_k=20)
4. if not vector_results and not keyword_results: # Resilient fallback
       vector_results = ANN_search(query_vec, filter=None, top_k=20)
       keyword_results = FTS_search(norm.expanded_keyword, filter=None, top_k=20)
5. candidate_pool = Reciprocal_Rank_Fusion(vector_results, keyword_results, k=60, top_k=20)
6. reranked = Reranker.arerank(query=norm.expanded_vector, chunks=candidate_pool, top_k=5)
   -> Routes to Jina Reranker v2 API (with local CrossEncoder fallback)
   -> Updates JinaTokenTracker with API token consumption against 10M quota
7. if reranked[0].score < CONFIDENCE_THRESHOLD (0.55):
       return fallback_response() # Trust layer: zero hallucination
   else:
       return generate_answer(query, reranked[:5]) # Gemini Flash synthesis with citations & tables
```
`CONFIDENCE_THRESHOLD` is strictly calibrated at `0.55`.

### 5.4 Conflict Detection
When two active documents are tagged with overlapping `department` + a matching document "type" heuristic (e.g., both classified as "exam schedule" via a lightweight classifier or filename/keyword rule) and their content disagrees on a extracted key fact (date, amount), flag a `conflicts` row instead of silently ingesting both as retrievable. Documents in `conflicts` are strictly excluded from retrieval until administrative resolution.

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
| `GET` | `/admin/jina-usage` | Token usage statistics across embeddings & reranker vs 10M free limit |

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

- **Local Development (Non-Docker App Execution):** Native Python virtual environment (Python 3.11+) running FastAPI via `uvicorn` and React frontend (Node 20+) via Vite (`npm run dev`), connected to local PostgreSQL with pgvector, with background tasks executing in-process (Celery eager mode).
- **Staging & Production:** Docker Compose / containerized single VM (or Render/Railway) running FastAPI, Postgres+pgvector, Redis, Celery worker, and built static frontend.
- **CI/CD:** GitHub Actions — run backend tests (`pytest`, `ruff`, `black`) and frontend tests (`npm test`, `npm run lint`) directly on host runners on PR; build Docker images on merge to `main`.
- **Secrets:** LLM/embedding API keys stored in environment variables / GitHub Actions secrets, never committed.

---

## 11. Open Technical Decisions

- **[Resolved] Reranker Choice:** Adopted Jina Reranker v2 (`jina-reranker-v2-base-multilingual`) via API with local `ms-marco-MiniLM-L-6-v2` fallback (ADR-015). Delivers sub-150ms cross-encoder precision without CPU bottlenecks.
- **[Resolved] Embedding Dimensionality & Schema:** Standardized on 1024 dimensions across both `jina-embeddings-v3` and local `BAAI/bge-m3`, allowing seamless zero-migration switching and unified `vector(1024)` HNSW indexing (ADR-014, ADR-015).
- Whether conflict-type classification (Section 5.4) is a rule-based heuristic or a small trained classifier — start rule-based, revisit if false-positive rate is high.
