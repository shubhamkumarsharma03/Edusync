# AGENTS.md

Instructions for AI coding agents (Claude Code and similar) working in this repository. Read this before making changes. Human contributors: see `EduSync_PRD.md` and `EduSync_Technical_Design_Document.md` for product/technical context — this file only covers repo conventions and agent workflow.

---

## Project Summary

EduSync is a self-updating RAG chatbot that answers student questions from a college's institutional documents (exam schedules, circulars, syllabus, fee notices). The two things that make this different from a generic RAG tutorial project, and that agents must preserve in every change:

1. **Self-updating ingestion** — documents are re-checked on a schedule via content hashing; only changed chunks are re-embedded. Never "fix" a bug by re-embedding the whole corpus as a shortcut.
2. **Trust layer** — every answer must carry a source citation and a confidence score; below-threshold retrievals must return a fallback message, never a guessed answer. Do not remove or bypass this gate to "make tests pass."

---

## Repo Structure

```
/backend
  /api            FastAPI routes (chat, feedback, admin)
  /ingestion      Celery tasks: fetch, hash-diff, chunk, embed, upsert
  /retrieval      Hybrid search, reranking, confidence gating
  /models         Pydantic schemas + SQLAlchemy models
  /db             Migrations (Alembic), DDL
  /tests
/frontend
  /src
    /components   Chat UI, Admin dashboard
    /api          API client wrappers
  /tests
/docs
  EduSync_PRD.md
  EduSync_Technical_Design_Document.md
  Project_Synopsis.docx
/scripts          One-off dev/ops scripts (seed data, manual re-ingest trigger)
docker-compose.yml
```

If a change requires deviating from this layout, say so explicitly in the PR description rather than silently restructuring.

---

## Setup & Commands

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt --break-system-packages
uvicorn api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Full stack (dev)
docker compose up --build

# Tests
cd backend && pytest
cd frontend && npm test

# Lint / format
cd backend && ruff check . && black .
cd frontend && npm run lint
```

Always run the relevant test suite after a change before considering a task done. If a command above doesn't exist yet in the repo, that's a signal the environment isn't fully scaffolded — flag it rather than inventing a different one silently.

---

## Coding Conventions

**Python (backend/ingestion)**
- Style: `black` formatting, `ruff` linting. Type hints required on all function signatures.
- Pydantic models for all API request/response bodies — no raw dicts across the API boundary.
- Async endpoints (`async def`) for anything that calls the LLM, embedding API, or DB — this app is I/O-bound.
- Never hardcode API keys or DB URLs — read from environment variables (see `.env.example`).

**TypeScript/React (frontend)**
- Functional components + hooks only. No class components.
- Tailwind utility classes for styling — no separate CSS files unless a Tailwind config extension is genuinely needed.
- API calls go through `/src/api` wrappers, never inline `fetch` in components.

**SQL / migrations**
- All schema changes go through an Alembic migration — never hand-edit the schema directly in a running DB.
- Match the DDL conventions already in `EduSync_Technical_Design_Document.md` §4 (UUID primary keys, `TIMESTAMPTZ`, explicit `CHECK` constraints for status enums).

---

## Non-Negotiable Behaviors (do not "optimize away")

- **Confidence gate:** if reranked top-chunk score < `CONFIDENCE_THRESHOLD`, return the fallback response. Do not lower the threshold to reduce fallback rate without an explicit instruction — that trades hallucination risk for a better-looking demo number.
- **Citations:** every `/chat` response must include `sources[]` with `document`, `last_verified`, and `url`. If this is empty, the fallback path should have been used instead.
- **Conflict handling:** documents flagged in the `conflicts` table must stay excluded from retrieval until an admin resolves them. Do not auto-resolve conflicts programmatically.
- **Change-detection cost:** re-ingestion must only re-embed chunks belonging to changed documents (via `content_hash` comparison), not the full corpus, per TDD §5.1.

If a task seems to require violating one of these to "make it work," stop and flag it instead of quietly bypassing it.

---

## Testing Expectations

- New ingestion logic → add/extend unit tests for chunking boundaries and hash-diff behavior (`backend/tests/test_ingestion.py`).
- New retrieval logic → test against the fixture question set in `backend/tests/fixtures/eval_questions.json` (the same 100-question set referenced in the PRD's evaluation harness).
- New API endpoint → add a request/response contract test (FastAPI `TestClient`).
- UI changes → snapshot or interaction test in `frontend/tests`, plus a manual check that citations/confidence still render.

---

## PR / Change Description Expectations

When an agent completes a task, the summary should state:
1. Which functional requirement (FR-#) or milestone (M#) from the PRD this addresses, if applicable.
2. Any deviation from the TDD's stated design and why.
3. Whether the confidence gate / citation / conflict-exclusion behaviors were touched, and how they were verified to still hold.

---

## Things Agents Should Ask About Rather Than Assume

- Whether the college has an official document export/API (referenced as an open question in the PRD §10) — don't build a scraper against a URL structure without confirming it's stable.
- Any change to `CONFIDENCE_THRESHOLD` — this is a product decision, not just a tuning parameter.
- Adding a new source type beyond PDF/HTML/sheet — the `documents.source_type` CHECK constraint needs a matching migration.
