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
   - Automated crawler for all 13+ ECA departments and administrative sections.
   - **Early SHA-256 Short-Circuiting**: Hashes raw binary file bytes immediately upon download, skipping parsing and OCR completely for unchanged documents (sub-millisecond skip).
   - **Page-Level Hybrid PDF Parsing**: Selective OCR per page (pages with high native text density stay on fast PyMuPDF; low-density or raster image pages route to Baidu PaddleOCR-VL).
   - **Repeated Markdown Table Column Headers**: Large timetables and fee schedules split strictly on row boundaries while repeating Markdown table column headers (`| Col 1 | Col 2 |\n|---|---|`) at the top of every chunk.
   - **Institutional Boilerplate Stripping**: Targeted regex heuristics strip repeated letterheads, page footers ("Page 1 of 2"), and trailing distribution lists ("Copy to: 1. Principal...").
   - **Automatic Corrigendum & Revision Linking**: Detects revised schedules and corrigenda, auto-superseding older notices in the same department/topic.
   - **Model-Safe Contextual Header Budgeting**: Injects `[Notice: ... | Ref: ... | Date: ... | Dept: ...]` into every chunk while keeping total tokens strictly $\le 550$ (safe headroom below embedding model sequence length).
   - Persistent SHA-256 Markdown OCR cache eliminates redundant OCR execution.
   - High-speed URL-to-markdown extraction powered by **Jina Reader API** (`https://r.jina.ai/`).
2. **Institutional Trust Layer & Confidence Gating**:
   - Every answer includes verified **Source Citations** with official document URLs, department origin, and verification timestamps.
   - Three-tier confidence gating ($\ge 0.75$ high confidence direct, $0.40 - 0.75$ medium confidence with student caveat, $< 0.40$ official fallback).
   - Single-call production Gemini evidence check achieving **100.00% Abstention Accuracy** on unanswerable and near-miss questions.
3. **Intent-Routed Hybrid Search & Jina AI Cloud Acceleration**:
   - Structure-aware chunking with heading hierarchy breadcrumbs (`[Context: # > ## > ###]`).
   - Domain-specific query normalizer extracting department, semester, and topic intent.
   - Fuses Dense Vector embeddings (1024-dim via pgvector HNSW) and PostgreSQL Full-Text Search (BM25 with stored tsvector and GIN trigram index) via **Reciprocal Rank Fusion (RRF)** with candidate pool scaling (`candidate_k=40`, `top_k=25`) and soft recency/department multipliers.
   - Dual-provider embedding architecture: **Jina Embeddings v3** (`jina-embeddings-v3`, task-specific passage/query adapters) with transparent local **BAAI/bge-m3** fallback.
   - Dual-provider reranker architecture: **Jina Reranker v2** (`jina-reranker-v2-base-multilingual`) with local **ms-marco-MiniLM-L-6-v2** fallback to select top 5 chunks.
   - Context-aware multi-turn conversational query rewriter (`gemini-3.5-flash-lite` -> `gemini-3.8-flash` -> `gemini-3.5-flash`).
   - Synthesized via **Gemini Flash** with clean markdown tables.
4. **Token Quota Monitoring & Real-Time Tracking**:
   - Thread-safe `JinaTokenTracker` monitors combined token usage across embeddings and reranking against Jina's 10,000,000 free-tier limit.
   - Inspected live via `GET /admin/jina-usage`.
5. **Dedicated Admin Panel & Live Pipeline Inspector**:
   - Standalone admin dashboard to manage data sources, view live ECA circular feeds, trigger on-demand synchronization, and inspect step-by-step pipeline execution in real time with 5-second auto-polling.
   - **100% Chronological Portal Ordering**: Documents in the admin explorer appear in the exact publication sequence (`notice_date DESC, notice_sno DESC, portal_id DESC`) as the live college portal.
   - **Ground-Truth Title Persistence**: Persists clean official notice titles natively in PostgreSQL, eliminating OCR letterhead noise (`ENGINEERING COLLEGE AJMER`).
6. **100% Offline Local Fallback**:
   - If `JINA_API_KEY` is not provided, the pipeline executes completely offline using cached local models (`backend/models_cache/bge-m3` and `ms-marco-MiniLM-L-6-v2`).

---

## Architecture

```mermaid
flowchart TD

    %% React Client
    subgraph group_client["React Client"]
        node_react_app["Student & Admin UI<br/>React App<br/>[App.tsx]"]
        node_client_chat_api["Chat API Client<br/>[chat.ts]"]
        node_client_sources_api["Sources API Client<br/>[sources.ts]"]
        node_admin_panel["Source Admin Panel<br/>React Component"]
    end

    %% FastAPI Service
    subgraph group_api["FastAPI Service"]
        node_fastapi["FastAPI Entry<br/>[main.py]"]
        node_chat_routes["Chat Routes<br/>[chat.py]"]
        node_admin_routes["Source Administration<br/>[admin_sources.py]"]
        node_department_routes["Departments Routes<br/>[departments.py]"]
    end

    %% Synchronization Pipeline
    subgraph group_ingestion["Synchronization Pipeline"]
        node_sync_pipeline["Fetch, Parse & Chunk Pipeline<br/>[pipeline.py]"]
        node_fetchers["Official Source Fetchers<br/>[factory.py]"]
        node_change_upsert["Change Detection & Upsert<br/>[change_detector.py]"]
        node_embedder["Chunk Embeddings<br/>[embedder.py]"]
        node_sync_tasks["Async Sync Execution<br/>[tasks.py]"]
        node_worker["Worker Entry<br/>[worker.py]"]
    end

    %% Retrieval and Answers
    subgraph group_retrieval["Retrieval and Answers"]
        node_retrieval_flow["Normalize, Hybrid Search & Rerank<br/>[hybrid_search.py]"]
        node_confidence_gate["Evidence Confidence Gate<br/>[confidence_gate.py]"]
        node_generator["Cited Answer Generator<br/>[generator.py]"]
    end

    %% Durable Storage
    subgraph group_storage["Durable Storage"]
        node_postgres[("PostgreSQL + pgvector<br/>[session.py]")]
        node_alembic["Versioned Schema Migrations<br/>[env.py]"]
    end

    %% External Services
    subgraph group_external["External Services"]
        node_official_sources["ECA Portal & Official URLs<br/>[ecajmer_fetcher.py]"]
        node_local_models["Local Embedding & Reranker Models<br/>Sentence-Transformers<br/>[download_models.py]"]
        node_gemini["Google Gemini<br/>Answer Synthesis API<br/>[config.py]"]
    end

    %% Client Connections
    node_react_app -->|"uses"| node_client_chat_api
    node_react_app -->|"uses"| node_client_sources_api
    node_admin_panel -->|"manages sources"| node_client_sources_api

    %% API Connections
    node_client_chat_api -->|"chat requests"| node_chat_routes
    node_client_sources_api -->|"admin requests"| node_admin_routes

    node_fastapi -->|"mounts"| node_chat_routes
    node_fastapi -->|"mounts"| node_admin_routes
    node_fastapi -->|"mounts"| node_department_routes

    %% Chat and Retrieval
    node_chat_routes -->|"retrieves evidence"| node_retrieval_flow
    node_retrieval_flow -->|"dense + keyword search"| node_postgres
    node_retrieval_flow -->|"reranks"| node_local_models
    node_retrieval_flow -->|"ranked evidence"| node_confidence_gate
    node_confidence_gate -->|"accepted evidence"| node_generator
    node_generator -->|"synthesizes answer"| node_gemini

    %% Synchronization Workflow
    node_admin_routes -->|"starts synchronization"| node_sync_tasks
    node_sync_tasks -->|"local async"| node_sync_pipeline
    node_sync_tasks -.->|"production tasks"| node_worker
    node_worker -->|"executes"| node_sync_pipeline

    %% Ingestion Workflow
    node_sync_pipeline -->|"retrieves"| node_fetchers
    node_fetchers -->|"fetches"| node_official_sources
    node_sync_pipeline -->|"chunks content"| node_embedder
    node_embedder -->|"uses"| node_local_models
    node_embedder -->|"vectors"| node_change_upsert
    node_change_upsert -->|"upserts provenance & chunks"| node_postgres

    %% Database Migrations
    node_alembic -->|"evolves schema"| node_postgres

    %% Styling
    classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a
    classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554
    classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
    classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d
    classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337
    classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81
    classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a

    class node_react_app,node_client_chat_api,node_client_sources_api,node_admin_panel toneBlue
    class node_fastapi,node_chat_routes,node_admin_routes,node_department_routes toneAmber
    class node_sync_pipeline,node_fetchers,node_change_upsert,node_embedder,node_sync_tasks,node_worker toneMint
    class node_retrieval_flow,node_confidence_gate,node_generator toneRose
    class node_postgres,node_alembic toneIndigo
    class node_official_sources,node_local_models,node_gemini toneTeal
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
pytest              # Run full async test suite (117 tests)
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

## Repository Structure

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

## Project Documentation

- [EduSync Product Requirements Document (PRD)](docs/EduSync_PRD.md)
- [Technical Design Document (TDD)](docs/EduSync_Technical_Design_Document.md)
- [Architecture Decision Log (ADRs)](docs/decision.md)
- [Implementation Plan](docs/implementation_plan.md)
- [Agent & Contributor Guide](AGENTS.md)


