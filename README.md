# EduSync 🎓

> **Self-Updating Retrieval-Augmented Knowledge Base Chatbot for Institutional Documents**  
> *B.Tech Final Year Project — Engineering College Ajmer*

---

## 📌 Overview

EduSync is an institutional AI assistant designed to eliminate misinformation and communication delays for college students. It continuously monitors, synchronizes, parses, and answers student questions regarding **mid-term and end-term exam schedules, official department circulars, syllabi, fee notices, and academic orders** directly from the official Engineering College Ajmer (`ecajmer.ac.in`) portal.

### 🌟 Key Features

1. **Self-Updating Ingestion Pipeline**:
   - Automated crawler for all 13+ ECA departments and sections.
   - SHA-256 content hashing to re-embed **only modified circular chunks**, eliminating costly full re-indexing.
2. **Institutional Trust Layer & Confidence Gating**:
   - Every answer includes verified **Source Citations** with official document URLs, department origin, and verification timestamps.
   - Cross-Encoder confidence gate (`0.55` threshold) returns a safe fallback message if no verified information is found, strictly preventing hallucinations.
3. **High-Performance Hybrid Search**:
   - Fuses Dense Vector embeddings (pgvector) and PostgreSQL Full-Text Search (BM25) via **Reciprocal Rank Fusion (RRF)**.
   - Rescored with a Cross-Encoder Reranker (`ms-marco-MiniLM-L-6-v2`) and synthesized via **Gemini 3.6 Flash**.
4. **Dedicated Admin Panel (`/admin`)**:
   - Modern, standalone admin dashboard to manage data sources, view live ECA circular feeds, trigger on-demand synchronization, and monitor chunk statistics.
5. **100% Offline Local Model Caching**:
   - Neural network models (`all-MiniLM-L6-v2` and `ms-marco-MiniLM-L-6-v2`) are stored locally (~170 MB) with zero external dependency on Hugging Face Hub during runtime.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `google-genai` |
| **Database & Vector Store** | PostgreSQL 16+ with `pgvector` extension, SQLAlchemy 2.0 (Async), Alembic |
| **Search & ML** | Sentence-Transformers (`all-MiniLM-L6-v2`), Cross-Encoder (`ms-marco-MiniLM-L-6-v2`), Rank-BM25 |
| **Document Processing** | PyMuPDF (`fitz`), Beautiful Soup 4, HTTPX |
| **Background Tasks** | Async In-Process Workers (Local Dev) / Celery & Redis (Production) |

---

## 🚀 Getting Started (Local Development)

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

# 4. Download local AI models (~170 MB total)
python scripts/download_models.py

# 5. Configure environment
# Copy backend/.env.example to backend/.env and add your GEMINI_API_KEY:
# GEMINI_API_KEY=your_gemini_api_key_here
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edusync

# 6. Run database migrations
alembic upgrade head

# 7. Start the FastAPI server
uvicorn api.main:app --reload --port 8000
```
- **API Documentation (Swagger UI):** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/health`

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
2. Click **"Preload All Defaults"** to populate all 13 official ECA departmental sources (CSE, IT, Exam Section, Registrar, CE, EE, etc.).
3. Click the **Play button (▶)** next to any source (e.g. **#1 CSE Circulars**) to fetch, parse, embed, and store official notices in PostgreSQL.
4. Go back to the Chat interface at **`http://localhost:5173`** and ask questions (e.g., *"What is the recent mid-term timetable for CSE?"*).

---

## 🧪 Testing & Code Quality

### Backend
```bash
cd backend
pytest              # Run full async test suite (49 tests)
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


