# EduSync 🎓

> **Self-Updating Retrieval-Augmented Knowledge Base Chatbot for Institutional Documents**  
> *B.Tech IT Final Year Project — Engineering College Ajmer*

---

## 📌 Overview

EduSync is an institutional AI assistant that answers student queries about exam schedules, circulars, syllabi, fee notices, and official announcements by retrieving verified answers from a continuously synchronized knowledge base.

### Key Highlights
- **Self-Updating Ingestion**: Scheduled SHA-256 hash diffing detects changed notices and re-embeds only modified chunks.
- **Trust Layer & Confidence Gating**: Every answer includes source citations (`document`, `last_verified`, `url`). Queries below confidence threshold return safe fallback responses rather than hallucinations.
- **Conflict Handling**: Discrepant notices are flagged for administrative resolution and excluded from retrieval until resolved.
- **Zero-Docker Native Dev**: Run the full stack natively with Python 3.11+ and Node 20+ connected to local PostgreSQL with `pgvector`.

---

## 🛠️ Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons
- **Backend API**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- **Database & Vectors**: PostgreSQL 16+ with `pgvector` extension, SQLAlchemy 2.0 (async), Alembic
- **ML & Search**: Sentence-Transformers (`all-MiniLM-L6-v2`), BM25, Cross-Encoder (`ms-marco-MiniLM-L-6-v2`), Anthropic Claude 3.5 Sonnet / OpenAI GPT-4o-mini
- **Document Processing**: Playwright, PyMuPDF (`fitz`), PaddleOCR (PP-StructureV3)
- **Background Tasks**: Celery (Eager mode for dev / Redis for prod)

---

## 🚀 Quick Start (Native Local Development)

### 1. Prerequisites
- Python 3.11+ (or 3.12 / 3.13)
- Node.js 20+ LTS
- PostgreSQL with `pgvector` enabled (`CREATE EXTENSION vector;`)

### 2. Environment Configuration
```powershell
cp .env.example .env
```
Ensure `DATABASE_URL` matches your local PostgreSQL credentials (e.g. `postgresql+asyncpg://postgres:password@localhost:5432/edusync`).

### 3. Backend Setup & Run
```powershell
cd backend
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn api.main:app --reload
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### 4. Frontend Setup & Run
```powershell
cd frontend
npm install
npm run dev
```
- Web App: `http://localhost:5173`

---

## 🧪 Testing & Linting

### Backend
```powershell
cd backend
pytest              # Run async contract tests
ruff check .        # Lint check
black --check .     # Formatting check
```

### Frontend
```powershell
cd frontend
npm test            # Run Vitest suite
npm run build       # Verify TypeScript & Vite build
```

---

## 📚 Project Documentation

- [EduSync PRD (Product Requirements)](file:///D:/Projects/EduSync/docs/EduSync_PRD.md)
- [Technical Design Document (TDD)](file:///D:/Projects/EduSync/docs/EduSync_Technical_Design_Document.md)
- [Architecture Decision Log (ADRs)](file:///D:/Projects/EduSync/docs/decision.md)
- [Step-by-Step Implementation Plan](file:///D:/Projects/EduSync/docs/implementation_plan.md)
- [Agent & Contributor Guide](file:///D:/Projects/EduSync/AGENTS.md)
