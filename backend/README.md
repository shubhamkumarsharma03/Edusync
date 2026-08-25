# EduSync Backend ⚙️

FastAPI asynchronous backend for the EduSync self-updating RAG knowledge base chatbot.

---

## 📌 Architecture & Modules

```
/backend
  /alembic        Alembic migration scripts for PostgreSQL & pgvector schema
  /api            FastAPI routes, dependency injection, and configuration
    /routes       /chat, /admin/sources, /health
  /db             Async SQLAlchemy engine & session maker
  /ingestion      Crawlers, PyMuPDF parser, SHA-256 hash-diffing, and embedding
    /fetchers     ecajmer_fetcher.py (ECA institutional portal scraper)
  /models         SQLAlchemy ORM models (Document, Chunk, Conflict, IngestionSource)
  /retrieval      HybridSearcher (pgvector + BM25 via RRF), CrossEncoderReranker, ConfidenceGate
  /scripts        download_models.py, seed_sources.py
  /tests          Pytest async unit, mock, and integration test suite
```

---

## 🚀 Setup & Execution

### 1. Python Virtual Environment
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Download Local AI Models (~170 MB)
```bash
python scripts/download_models.py
```
This downloads `all-MiniLM-L6-v2` and `ms-marco-MiniLM-L-6-v2` into `backend/models_cache/` for offline, zero-warning CPU execution.

### 3. Database Migrations
```bash
alembic upgrade head
```

### 4. Run Development Server
```bash
uvicorn api.main:app --reload --port 8000
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/chat` | Grounded RAG query endpoint returning synthesized answer & citations |
| `GET` | `/admin/sources` | List all configured data source endpoints with statistics |
| `POST` | `/admin/sources` | Register a new prioritized institutional source URL |
| `PUT` | `/admin/sources/{id}` | Update source configuration (limits, active state, priority) |
| `DELETE` | `/admin/sources/{id}` | Remove a data source from ingestion schedule |
| `POST` | `/admin/sources/{id}/fetch` | Trigger on-demand crawler & embedding task for a source |
| `POST` | `/admin/sources/seed-defaults` | Preload all 13 official ECA departmental sources |
| `GET` | `/health` | System health check (DB connectivity & status) |

---

## 🧪 Testing & Code Quality

```bash
pytest              # Run all 49 async tests
ruff check .        # Lint check
black --check .     # Code format check
```

