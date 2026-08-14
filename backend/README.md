# EduSync Backend

FastAPI asynchronous backend for the EduSync self-updating RAG knowledge base chatbot.

## Structure

```
/backend
  /api            FastAPI routes & configuration
  /ingestion      Crawl, parse, hash-diff, chunk, and embed workers
  /retrieval      Hybrid search (BM25 + pgvector), reranking, confidence gating
  /models         SQLAlchemy async ORM models & Pydantic schemas
  /db             Alembic migrations
  /tests          Pytest async test suite
```

## Running Locally

```powershell
# Activate virtualenv
.\.venv\Scripts\Activate.ps1

# Run migrations
alembic upgrade head

# Start server with auto-reload
uvicorn api.main:app --reload --port 8000
```
