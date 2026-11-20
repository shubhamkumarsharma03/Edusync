# Product Requirements Document (PRD)
## EduSync — Self-Updating Retrieval-Augmented Knowledge Base Chatbot for College Information Systems

**Version:** 1.0
**Status:** Draft
**Owner:** Shubham Sharma + Team (4-member B.Tech IT Final Year Project)
**Last Updated:** July 25, 2026

---

## 1. Overview

### 1.1 Summary
EduSync is a chatbot that answers student questions about college information — exam schedules, fee circulars, syllabus, placement notices, and administrative announcements — by retrieving answers from an automatically maintained, always-current knowledge base, rather than a static one that goes stale after deployment.

### 1.2 Problem Statement
College information is scattered across the website, PDF circulars, notice boards, and department group chats. Students rely on outdated screenshots and word-of-mouth, causing missed deadlines and repeated queries to already-overloaded staff. Existing chatbot solutions (plain LLMs or naive RAG) hallucinate under uncertainty, go stale the moment a source document changes, and can't tell verified information apart from outdated duplicates in the same knowledge base.

### 1.3 Goal
Build a chatbot whose knowledge base updates itself automatically when source documents change, cites its sources, and refuses to answer rather than guess when confidence is low.

### 1.4 Non-Goals (v1)
- Not a general-purpose assistant — scoped strictly to institutional/college information.
- Not building a custom LLM — uses an existing LLM API (Claude/OpenAI) as the generation layer.
- Not handling voice input/output in v1.
- Not integrating with proctored exam systems or grade databases (privacy/scope boundary).
- Not supporting multi-college/multi-tenant use in v1 — single institution only.

---

## 2. Target Users & Personas

| Persona | Needs | Pain Today |
|---|---|---|
| **Student (primary user)** | Fast, accurate answers to "when," "how," "where" questions about college processes | Digs through WhatsApp groups, outdated PDFs, or asks faculty directly |
| **Faculty/Admin Coordinator** | Fewer repetitive student queries; a way to publish updates once | Answers the same question 50 times per notice |
| **Department Admin (content owner)** | Simple way to upload/update a document and trust it will propagate | No visibility into whether students are seeing current info |
| **Project Team (dev/maintainer)** | Clear ingestion and evaluation tooling to maintain and improve the system | N/A — building from scratch |

---

## 3. Success Metrics

| Metric | Target (v1 / Sem 7) | Target (v2 / Sem 8) | Current Verified Benchmark (63-Query Evaluation Suite) |
|---|---|---|---|
| Retrieval Recall@5 | ≥ 70% | ≥ 85% | **100.00%** |
| Retrieval Recall@10 | ≥ 80% | ≥ 90% | **100.00%** |
| MRR (Mean Reciprocal Rank) | ≥ 0.70 | ≥ 0.85 | **0.9464** |
| Answer accuracy / Correctness | ≥ 75% | ≥ 90% | **74.60%** (100% on unanswerables) |
| Abstention Accuracy (Unanswerables) | ≥ 85% | ≥ 95% | **100.00%** (Zero hallucination) |
| Freshness-propagation delay | < 24 hours (batch) | < 1 hour (near real-time) | Sub-second hash diff + instant API crawl |
| Duplicate/conflicting-source incidents | Tracked, not yet minimized | < 2% of queries | Automated Corrigendum & Supersession Linking |

---

## 4. Functional Requirements

### 4.1 Document Ingestion
- **FR-1:** System shall ingest documents from institutional sources: primarily downloadable PDFs (~95% of notices, timetables, syllabi, fee schedules), alongside HTML announcement pages and structured sheets (CSV/Excel).
- **FR-2:** Each ingested document shall be tagged with metadata: `source_url`, `source_type`, `department`, `document_owner`, `ingested_at`, `content_hash`.
- **FR-3:** System shall chunk documents into retrieval-sized segments (target: 300–500 tokens per chunk) preserving section context (e.g., don't split a table mid-row).

### 4.2 Change Detection & Self-Updating
- **FR-4:** A scheduled job (cron, configurable interval — default every 6 hours) shall re-check all registered sources.
- **FR-5:** System shall compute a content hash per source document; if the hash differs from the last stored hash, the document is marked "changed" and queued for re-ingestion.
- **FR-6:** Only changed/new chunks shall be re-embedded (not the entire knowledge base) to keep update cost proportional to change size.
- **FR-7:** When a document is deleted or superseded at the source, its chunks shall be marked `stale` (not immediately hard-deleted) and excluded from retrieval, with a grace-period audit log.
- **FR-8:** Every chunk shall carry a `last_verified` timestamp visible to the admin dashboard.

### 4.3 Source-of-Truth Registry
- **FR-9:** Each document type (e.g., "exam schedule," "fee circular") shall map to exactly one designated source/owner in the registry.
- **FR-10:** If two ingested documents claim authority over the same fact (e.g., two different exam-date PDFs), the system shall flag a conflict in the admin dashboard rather than silently retrieving both.
- **FR-11:** Conflicting documents shall be resolved by admin action (mark one authoritative) before both are eligible for retrieval.

### 4.4 Retrieval & Generation
- **FR-12:** System shall use hybrid retrieval (keyword/BM25 + semantic/embedding similarity) to fetch candidate chunks.
- **FR-13:** Retrieved candidates shall be reranked before being passed to the LLM.
- **FR-14:** The LLM shall generate an answer grounded only in retrieved chunks, with an explicit system instruction to avoid unsupported claims.
- **FR-15:** If no retrieved chunk clears a minimum relevance/confidence threshold, the system shall respond with a fallback ("I don't have verified information on this — please check with [department] or [source link]") instead of guessing.
- **FR-16:** Every answer shall include a citation: which source document and its `last_verified` date.

### 4.5 Student Chat Interface
- **FR-17:** Web-based chat UI accepting natural-language questions.
- **FR-18:** Each answer displays: response text, source citation(s), freshness date, and a confidence indicator (High/Medium/Low or numeric).
- **FR-19:** Chat history persists per session (not necessarily per account in v1).
- **FR-20:** UI shall support a "Was this helpful?" feedback control (thumbs up/down) to log for future evaluation.

### 4.6 Admin Dashboard
- **FR-21:** View list of all ingested sources with status (fresh / stale / conflicted / pending).
- **FR-22:** Manually trigger re-ingestion of a specific source.
- **FR-23:** Resolve flagged conflicts (choose authoritative document).
- **FR-24:** View basic usage analytics: query volume, top unanswered questions, feedback scores.

### 4.7 Evaluation Harness (Sem 8 focus)
- **FR-25:** Maintain a fixed test set of ~100 real student questions with expected answers/sources.
- **FR-26:** Automated script to compute retrieval precision, answer accuracy (LLM-as-judge or manual), and freshness-propagation delay.
- **FR-27:** Ablation mode: run the same test set against a "static" (no self-update) version of the pipeline for comparison.

### 4.8 Institutional Notice Synchronization & Ingestion Fidelity
- **FR-28 (Exact Portal Chronological Alignment):** The admin explorer ("Stored in EduSync DB") shall display ingested notices in the exact chronological publication sequence (`notice_date DESC, notice_sno DESC, portal_id DESC`) as the official college portal feed. Even if older notices are ingested later, they must slot into their historical row.
- **FR-29 (Ground-Truth Notice Title Persistence):** The system shall capture clean notice titles from portal HTML anchor text and API payloads (`entry["title"]`), persisting `documents.title` natively to prevent scanned PDF letterhead noise (`ENGINEERING COLLEGE AJMER`) from appearing as titles.
- **FR-30 (Page-Level Hybrid PDF Parsing & Table Splitting):** PDF parsing decisions shall be made per-page (native text density check with selective OCR fallback); large tables shall be split on row boundaries with repeated Markdown table column headers (`| Col 1 | Col 2 |\n|---|---|`) across chunks.
- **FR-31 (Corrigendum & Revision Auto-Linking):** Notices indicating updates (`Revised`, `Corrigendum`, `Postponed`) shall be automatically linked to prior active notices in the same department/topic to supersede outdated schedules.
- **FR-32 (Contextual Header & Safe Token Budget):** All chunks shall carry a concise metadata header `[Notice: ... | Ref: ... | Date: ... | Dept: ...]` with total chunk token count constrained to $\le 550$ tokens.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Answer latency < 5 seconds for 95% of queries |
| **Scalability** | Support at least 500 documents and 50 concurrent chat sessions without degradation |
| **Reliability** | Ingestion job failures must be logged and retried (max 3 attempts) without crashing the pipeline |
| **Security** | No student PII stored beyond session-scoped chat logs; admin dashboard behind authentication |
| **Maintainability** | Ingestion pipeline and retrieval logic should be modular enough to swap vector DB or LLM provider without a full rewrite |
| **Auditability** | All document changes, conflict resolutions, and re-ingestion events logged with timestamps |

---

## 6. System Architecture (Reference)

```
Data Sources (website, PDFs, sheets)
        │
        ▼
Scheduled Scraper/Watcher → Change Detection (hash diff) → Chunking + Metadata Tagging → Source-of-Truth Registry
        │
        ▼
Embedding Model → Vector Database → Freshness Timestamps
        │
        ▼
Hybrid Search (keyword + semantic) → Reranker → LLM Answer Generation → Source Citation + Confidence Check
        │
        ▼
Chat UI (student) ←──────────────────────────────→ Admin Dashboard
```

*(Full diagram already produced separately as `architecture.png` / Mermaid source in the project synopsis.)*

---

## 7. Data Model (Simplified)

**`documents`**
`id, source_url, source_type, department, owner, content_hash, ingested_at, status (fresh/stale/conflicted)`

**`chunks`**
`id, document_id (FK), content, embedding_vector, last_verified, token_count`

**`conflicts`**
`id, document_ids[], detected_at, resolved_by, resolved_at, resolution_note`

**`queries_log`**
`id, question, retrieved_chunk_ids[], answer, confidence_score, feedback (up/down/null), timestamp`

---

## 8. Milestones & Timeline

| Milestone | Timeframe | Key Deliverable |
|---|---|---|
| M1 — Scoping & Literature Review | Sem 7, Wk 1–2 | Finalized scope, tech stack, literature summary |
| M2 — Core RAG Pipeline | Sem 7, Wk 3–6 | Working ingestion → retrieval → generation pipeline |
| M3 — Self-Updating Layer + Frontend | Sem 7, Wk 7–9 | Change-detection pipeline, chat UI |
| M4 — Testing & Sem 7 Submission | Sem 7, Wk 10–12 | Tested prototype, interim report |
| M5 — Scale & Robustness | Sem 8, Wk 1–3 | Handles larger/messier document sets |
| M6 — Formal Evaluation & Ablation | Sem 8, Wk 4–6 | Static vs. self-updating RAG comparison report |
| M7 — Deployment & Real Usage | Sem 8, Wk 7–9 | Live deployment, real user feedback |
| M8 — Publication & Final Submission | Sem 8, Wk 10–12 | Paper draft, final report, demo |

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Source documents have inconsistent formats (scanned PDFs, tables) | Ingestion breaks or produces bad chunks | Add OCR fallback; manually curate a "clean" source set for MVP, expand later |
| LLM API costs scale with usage | Budget overrun during testing/demo | Cache repeated queries; use smaller/cheaper model for reranking, larger only for final generation |
| College sources change format/URL without notice | Ingestion silently fails | Add ingestion health alerts (failed fetch count) visible on admin dashboard |
| Team members' bandwidth conflicts with coursework | Slipped milestones | Weekly task board (Trello/GitHub Projects) with owner + due date per FR |
| Evaluation test set is small (~100 Qs) | Metrics not statistically robust | Explicitly acknowledge as a limitation in the paper; supplement with real usage logs from Sem 8 deployment |

---

## 10. Open Questions

- Will the college provide any official API/export access to circulars, or is web scraping the only option?
- Should chat history be tied to a student login (college SSO) or remain anonymous/session-based in v1?
- What's the actual deployment target — a college-hosted server, or a public cloud instance the college links to?
- Who is the designated "document owner" for conflict resolution in practice — a faculty coordinator, or the project team during evaluation?

---

## 11. Appendix

- Related work: Lewis et al. (2020) RAG, Edge et al. (2024) GraphRAG, Xu et al. (2024) RECOMP.
- Reference diagrams: system architecture and two-semester timeline (Mermaid source available separately).
- Team roles (suggested): Person A — ingestion/change-detection; Person B — vector DB/retrieval; Person C — backend API/evaluation harness; Person D — frontend/UX/documentation.
