<p align="center">
  <img src="docs/assets/logo.png" alt="EduSync Logo" width="380" />
</p>

# EduSync

> **Self-Updating Retrieval-Augmented Knowledge Base Chatbot for Institutional Documents**  
> *B.Tech Final Year Project — Engineering College Ajmer*

---

## Overview

EduSync is an institutional AI assistant designed to eliminate misinformation and communication delays for college students. It continuously monitors, synchronizes, parses, and answers student questions regarding **mid-term and end-term exam schedules, official department circulars, syllabi, fee notices, and academic orders** directly from the official Engineering College Ajmer (`ecajmer.ac.in`) portal.

### Key Features

1. **Self-Updating Ingestion Pipeline**:
   - Automated crawler for all 13+ ECA departments and sections.
   - SHA-256 content hashing to re-embed **only modified circular chunks**, eliminating costly full re-indexing.
   - Baidu PaddleOCR-VL engine converts complex scanned documents into structured Markdown with preserved tables.
   - Persistent SHA-256 Markdown OCR cache eliminates redundant OCR execution.
   - High-speed URL-to-markdown extraction powered by **Jina Reader API** (`https://r.jina.ai/`).
2. **Institutional Trust Layer & Confidence Gating**:
   - Every answer includes verified **Source Citations** with official document URLs, department origin, and verification timestamps.
   - Cross-Encoder confidence gate (`0.55` threshold) returns a safe fallback message if no verified information is found, strictly preventing hallucinations.
3. **Intent-Routed Hybrid Search & Jina AI Cloud Acceleration**:
   - Structure-aware chunking with heading hierarchy breadcrumbs (`[Context: # > ## > ###]`).
   - Domain-specific query normalizer extracting department, semester, and topic intent.
   - Fuses Dense Vector embeddings (1024-dim via pgvector HNSW) and PostgreSQL Full-Text Search (BM25) via **Reciprocal Rank Fusion (RRF)** to retrieve top 20 candidate chunks.
   - Dual-provider embedding architecture: **Jina Embeddings v3** (`jina-embeddings-v3`, task-specific passage/query adapters) with transparent local **BAAI/bge-m3** fallback.
   - Dual-provider reranker architecture: **Jina Reranker v2** (`jina-reranker-v2-base-multilingual`) with local **ms-marco-MiniLM-L-6-v2** fallback to select top 5 chunks.
   - Synthesized via **Gemini Flash** with clean markdown tables.
4. **Token Quota Monitoring & Real-Time Tracking**:
   - Thread-safe `JinaTokenTracker` monitors combined token usage across embeddings and reranking against Jina's 10,000,000 free-tier limit.
   - Inspected live via `GET /admin/jina-usage`.
5. **Dedicated Admin Panel & Live Pipeline Inspector**:
   - Modern, standalone admin dashboard to manage data sources, view live ECA circular feeds, trigger on-demand synchronization, and inspect step-by-step pipeline execution in real time with 5-second auto-polling.
6. **100% Offline Local Fallback**:
   - If `JINA_API_KEY` is not provided, the pipeline executes completely offline using cached local models (`backend/models_cache/bge-m3` and `ms-marco-MiniLM-L-6-v2`).

---

## Architecture

```mermaid
flowchart TD
    subgraph DataSources ["1. Data Sources & Ingestion"]
        DS1["ecajmer.ac.in Department Portals"] --> CRAWL["Playwright Crawler / Jina Reader API"]
        CRAWL --> HASH["SHA-256 Content Hash Diff"]
        HASH -- "Unchanged (Hash Match)" --> SKIP["Update last_checked_at (0 Compute Cost)"]
        HASH -- "New or Modified" --> OCR["Baidu PaddleOCR-VL Engine"]
        OCR <--> OCACHE[("Persistent SHA-256 Markdown Cache")]
    end

    subgraph ChunkingAndEmbedding ["2. Structure-Aware Chunking & Embedding"]
        OCR --> MD["Structured Markdown with Headings & Tables"]
        MD --> CHUNKER["SemanticChunker with Breadcrumb Hierarchy"]
        CHUNKER --> ENT["Entity Extraction (semester, notice_sno, academic_year)"]
        CHUNKER --> BC["Inject Context Breadcrumbs: [Context: # > ## > ###]"]
        BC & ENT --> EMBED{"Embedding Provider"}
        EMBED -- "Jina API" --> JINA_EMBED["Jina Embeddings v3 (1024-d)<br/>task: 'retrieval.passage' (Batch: 32)"]
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
        RRF --> RERANK{"Reranker Provider"}
        RERANK -- "Jina API" --> JINA_RERANK["Jina Reranker v2<br/>jina-reranker-v2-base-multilingual<br/>Top 5 Chunks"]
        RERANK -- "Local Fallback" --> LOCAL_RERANK["CrossEncoder (ms-marco-MiniLM-L-6-v2)<br/>Top 5 Chunks"]
        JINA_RERANK & LOCAL_RERANK --> GATE{"Top Score >= CONFIDENCE_THRESHOLD (0.55)?"}
        GATE -- No --> FALLBACK["Safe Fallback Response (Zero Hallucination)"]
        GATE -- Yes --> LLM["LLM Synthesis (Gemini Flash) with Citations & Tables"]
    end

    subgraph QuotaManagement ["5. Quota Tracking"]
        JINA_EMBED -.-> TRACKER[("JinaTokenTracker<br/>10,000,000 Free Quota")]
        JINA_RERANK -.-> TRACKER
        TRACKER -.-> ADMIN_USAGE["GET /admin/jina-usage"]
    end

    subgraph PresentationLayer ["6. Presentation Layer"]
        LLM & FALLBACK --> CHAT_UI["Student Chat Interface"]
        DB_DOCS & DB_CHUNKS & ADMIN_USAGE --> ADMIN_UI["Admin Dashboard & Live Pipeline Inspector"]
    end
```

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `google-genai` |
| **Database & Vector Store** | PostgreSQL 16+ with `pgvector` extension (HNSW cosine index), SQLAlchemy 2.0 (Async), Alembic |
| **Embeddings** | Jina Embeddings v3 (`jina-embeddings-v3`, 1024-d) / BAAI/bge-m3 (local 1024-d offline fallback) |
| **Reranking** | Jina Reranker v2 (`jina-reranker-v2-base-multilingual`) / Cross-Encoder (`ms-marco-MiniLM-L-6-v2` fallback) |
| **Document Processing & OCR** | Baidu PaddleOCR-VL, Jina Reader API (`https://r.jina.ai/`), PyMuPDF (`fitz`), Persistent SHA-256 Cache |
| **Quota & Tracking** | `JinaTokenTracker` (10M free-tier quota pool monitoring), `/admin/jina-usage` |
| **Background Tasks** | Async In-Process Workers (Local Dev) / Celery & Redis (Production) |

---

## Getting Started (Local Development)

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 20+ LTS**
- **PostgreSQL 16+** with `pgvector` extension enabled

---

### 2. Database Setup

Create the local PostgreSQL database and enable `pgvector`:
```sql
CREATE DATABASE edusync;
\c edusync
CREATE EXTENSION IF NOT EXISTS vector;
```

---

### 3. Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create and activate virtual environment
# On Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# python3 -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download local AI models (BAAI/bge-m3 & ms-marco-MiniLM)
python scripts/manage_models.py

# 5. Configure environment
# Copy backend/.env.example to backend/.env and add your API keys:
# GEMINI_API_KEY=your_gemini_api_key_here
# JINA_API_KEY=your_jina_api_key_here  # Shared key for Jina Embeddings v3, Reranker v2 & Reader
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edusync

# 6. Run database migrations
alembic upgrade head

# 7. Start the FastAPI server
uvicorn api.main:app --reload --port 8000
```
- **API Documentation (Swagger UI):** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/health`
- **Jina Token Quota Inspector:** `http://localhost:8000/admin/jina-usage`

---

### 4. Frontend Setup

In a new terminal window:
```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Start Vite development server
npm run dev
```
- **Student Chat Assistant:** `http://localhost:5173`
- **Admin Data Sources Panel:** `http://localhost:5173/admin`

---

### 5. Ingesting Official Documents for First Use

1. Open the Admin Panel at **`http://localhost:5173/admin`** (or click **Data Sources** in the chat sidebar).
2. Click **"Preload All Defaults"** to populate all official ECA departmental sources (CSE, IT, Exam Section, Registrar, CE, EE, etc.).
3. Click the **Play button** next to any source (e.g. **#1 CSE Circulars**) to fetch, parse, embed, and store official notices in PostgreSQL.
4. Go back to the Chat interface at **`http://localhost:5173`** and ask questions (e.g., *"What is the recent mid-term timetable for CSE?"*).

---

## Testing & Code Quality

### Backend
```bash
cd backend
pytest              # Run full async test suite (95 tests)
ruff check .        # Linting validation
black --check .     # Code formatting check
```

### Frontend
```bash
cd frontend
npm test            # Run Vitest suite
npm run build       # Verify TypeScript & Vite production build
```

---

## 📁 Repository Structure

```
/backend
  /alembic          Database schema migrations (PostgreSQL + pgvector)
  /api              FastAPI endpoints (/chat, /admin/sources, /health)
  /db               Async SQLAlchemy database session setup
  /ingestion        Fetchers, PyMuPDF parser, hash-diffing, and chunk embedding
  /models           SQLAlchemy ORM models & Pydantic validation schemas
  /retrieval        Hybrid search (Vector + BM25), Cross-Encoder reranker, trust gate
  /scripts          Helper scripts (download_models.py, seed_sources.py)
  /tests            Pytest async unit and contract test suite
/frontend
  /src
    /api            HTTP client wrappers (chat.ts, sources.ts)
    /components     AdminSourcesPanel.tsx, UI components
    /App.tsx        Main Chat canvas & standalone /admin routing
  /tests            Frontend Vitest test suite
/docs               PRD, Technical Design Document, Architecture Decisions
.github/workflows   Continuous Integration (CI) configuration
```

---

## 📚 Project Documentation

- [EduSync Product Requirements Document (PRD)](docs/EduSync_PRD.md)
- [Technical Design Document (TDD)](docs/EduSync_Technical_Design_Document.md)
- [Architecture Decision Log (ADRs)](docs/decision.md)
- [Implementation Plan](docs/implementation_plan.md)
- [Agent & Contributor Guide](AGENTS.md)


