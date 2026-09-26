# DevForge — Implementation Phases

**IBM Bob 2.0 Hackathon | Phase 0 Planning**

---

## Overview

The build is divided into 6 implementation sessions (phases 1–6), each with a clear scope, deliverables, and IBM Bob feature demonstration plan.

**Rules:**
- No phase begins until the previous phase's gate criteria are verified working
- Optional features are not touched until all Phase 1–5 MUST items pass
- No API keys, passwords, or credentials in any committed file
- JS/TS verification is explicitly optional — Python is the only required target for the MVP
- Docker Compose is a Phase 5 deliverable, not Phase 1

---

## Phase 0 — Architecture (COMPLETE ✓)

**IBM Bob features demonstrated:**
- Document understanding (Bob read and understood the hackathon brief)
- Agent mode (Bob produced the full architecture from scratch)

**Deliverables:**
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/DATA_MODEL.md`
- [x] `docs/AGENT_ARCHITECTURE.md`
- [x] `docs/IMPLEMENTATION_PHASES.md`
- [x] `docs/MVP_SCOPE.md`
- [x] `docs/RISKS.md`
- [x] `README.md`

**Gate:** Human architect reviews and approves architecture before Phase 1 begins. ✓ Approved.

---

## Phase 1 — Foundation

**Bob session focus:** Scaffold the entire project skeleton — backend and frontend simultaneously  
**IBM Bob features demonstrated:**
- **Parallel tasks:** Bob simultaneously scaffolds `backend/` (FastAPI + DB) and `frontend/` (React + Vite)
- **Subagents:** Bob spawns a subagent for the frontend while the main agent builds the backend

**Backend deliverables:**
- `backend/pyproject.toml` — dependencies: `fastapi`, `uvicorn`, `sqlmodel`, `openai`, `python-dotenv`, `ruff`, `pytest`, `pytest-json-report`
- `backend/devforge/main.py` — FastAPI app: CORS configured, `/health` endpoint
- `backend/devforge/config.py` — `Settings` from environment variables via `pydantic-settings`; no hardcoded secrets
- `backend/devforge/db/models.py` — All SQLModel table definitions per `DATA_MODEL.md`
- `backend/devforge/db/session.py` — async DB session factory; tables created on startup
- `backend/devforge/api/analyze.py` — stub returning 501
- `backend/devforge/api/missions.py` — stub returning 501
- `backend/devforge/api/execute.py` — stub returning 501
- `backend/devforge/api/verify.py` — stub returning 501
- `backend/devforge/api/report.py` — stub returning 501
- `backend/devforge/utils/llm.py` — `LLMClient` wrapping `openai.AsyncOpenAI` with retry + JSON validation
- `backend/devforge/utils/file_tree.py` — directory walker, language detector, Python-focused
- `backend/devforge/utils/event_bus.py` — async `EventBus` with `asyncio.Queue`
- `.env.example` — documents `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `DATABASE_URL`

**Frontend deliverables:**
- `frontend/package.json` — React 18 + Vite + TypeScript + Tailwind + shadcn/ui + react-router-dom
- `frontend/vite.config.ts` — proxy `/api` to `http://localhost:8000`
- `frontend/src/main.tsx` — app entry point
- `frontend/src/App.tsx` — router with 4 page routes
- `frontend/src/pages/Dashboard.tsx` — placeholder (heading only)
- `frontend/src/pages/MissionBoard.tsx` — placeholder
- `frontend/src/pages/ExecutionView.tsx` — placeholder
- `frontend/src/pages/ImpactReport.tsx` — placeholder
- `frontend/src/types/index.ts` — TypeScript types matching all API response models
- `frontend/src/api/client.ts` — typed fetch wrapper functions for all API endpoints

**Phase 1 gate (must pass before Phase 2):**
- `uvicorn devforge.main:app --reload` starts with no errors
- `GET /health` returns `{"status": "ok"}`
- `pnpm dev` starts frontend with zero TypeScript errors
- All DB tables created on first backend startup (confirmed via SQLite browser or log)
- `LLMClient` initializes from env without error (no actual LLM call required in Phase 1)

---

## Phase 2 — Analyzer + Mission Builder

**Bob session focus:** Repository analysis and mission generation  
**IBM Bob features demonstrated:**
- **Document understanding:** Bob reads `ARCHITECTURE.md`, `DATA_MODEL.md`, and `AGENT_ARCHITECTURE.md` before writing
- **Subagents:** Bob spawns one subagent to write `analyzer.py`, another for `mission_builder.py`

**Deliverables:**
- `backend/devforge/agents/base.py` — `BaseAgent` abstract class with `run()` + `emit()`
- `backend/devforge/agents/analyzer.py` — `RepositoryAnalyzerAgent` (full implementation)
- `backend/devforge/agents/mission_builder.py` — `MissionBuilderAgent` (full implementation)
- `backend/devforge/utils/ruff_counter.py` — `count_ruff_errors(path: str) -> int`
- `backend/devforge/api/analyze.py` — `POST /analyze` functional endpoint
- `backend/devforge/api/missions.py` — `GET /missions`, `PATCH /missions/{id}` functional endpoints
- `backend/tests/fixtures/sample_repo/` — minimal Python project for testing (≥5 files, deliberate issues)
- `backend/tests/test_analyzer.py` — unit tests using fixture repo (no real LLM — mock `LLMClient`)
- `backend/tests/test_mission_builder.py` — unit tests with mock LLM responses

**Phase 2 gate (must pass before Phase 3):**
- `POST /analyze {"repo_path": "tests/fixtures/sample_repo"}` returns a valid `RepositorySnapshotOut`
- Snapshot contains: `file_count ≥ 1`, `lint_error_count ≥ 0`, `todo_count ≥ 0`, non-empty `analysis_summary`
- `GET /missions?repository_id=...` returns ≥3 missions after analysis
- All pytest tests pass (`uv run pytest backend/tests/`)
- Snapshot and missions survive server restart (SQLite confirmed)

---

## Phase 3 — Orchestrator + All Agents + VerificationRunner + SSE

**Bob session focus:** Parallel agent execution, live streaming, and verification  
**IBM Bob features demonstrated:**
- **Parallel tasks:** Bob simultaneously writes `implementer.py`, `tester.py`, `documenter.py`
- **Agent mode:** Bob builds the Orchestrator — mirrors DevForge's own parallel dispatch logic

**Why VerificationRunner is in Phase 3 (not Phase 4):**
`TesterAgent` delegates directly to `VerificationRunner`. Delivering TesterAgent without VerificationRunner would produce a non-functional agent. Both must be delivered together.

**Deliverables:**
- `backend/devforge/agents/orchestrator.py` — `AgentOrchestrator` with static `SUBTASK_TEMPLATES` and `asyncio.gather`
- `backend/devforge/agents/implementer.py` — `ImplementerAgent` (full file replacement via LLM + `py_compile` check)
- `backend/devforge/agents/tester.py` — `TesterAgent` (delegates to `VerificationRunner`)
- `backend/devforge/agents/documenter.py` — `DocumenterAgent` (Python AST + LLM docstring generation)
- `backend/devforge/verification/runner.py` — `VerificationRunner` dispatcher
- `backend/devforge/verification/python_checks.py` — `pytest --json-report` + `ruff check` → `VerificationResult`
- `backend/devforge/verification/generic_checks.py` — grep-based TODO/FIXME count
- `backend/devforge/verification/js_checks.py` — **stub only** (empty or `raise NotImplementedError`); full implementation is optional
- `backend/devforge/api/execute.py` — `POST /execute/{mission_id}` (creates run, dispatches Orchestrator) + `GET /execute/{run_id}/stream` (SSE endpoint)
- `frontend/src/components/AgentLogStream.tsx` — `EventSource` SSE consumer with reconnect
- `frontend/src/pages/ExecutionView.tsx` — live log page, functional

**Phase 3 gate (must pass before Phase 4):**
- `POST /execute/{mission_id}` creates an `execution_run` record and begins dispatching agents
- `GET /execute/{run_id}/stream` delivers SSE events to the browser
- Browser log shows interleaved events from ≥2 agents running in the same round
- `asyncio.gather` usage visible in server logs (timestamps confirm concurrent start)
- TesterAgent returns a real `VerificationResult` from `pytest` on the fixture repo

---

## Phase 4 — Differ + Impact Report

**Bob session focus:** Before/after measurement and the Impact Report page  
**IBM Bob features demonstrated:**
- **Parallel tasks:** Bob writes `snapshot/differ.py` + `frontend/ImpactReport.tsx` + `frontend/MetricDiff.tsx` simultaneously

**Deliverables:**
- `backend/devforge/snapshot/differ.py` — computes `ImpactReport` from two `RepositorySnapshot` records
- `backend/devforge/api/verify.py` — `POST /verify/{run_id}` (triggers post-execution snapshot + differ)
- `backend/devforge/api/report.py` — `GET /report/{repo_id}` (returns `ImpactReportOut`)
- `frontend/src/components/MetricDiff.tsx` — before/after metric card (value + delta + direction arrow)
- `frontend/src/pages/ImpactReport.tsx` — Impact Report page, functional

**Phase 4 gate (must pass before Phase 5):**
- After a complete Phase 3 mission run: `POST /verify/{run_id}` triggers post-execution snapshot and returns `VerificationResult`
- `GET /report/{repo_id}` returns `ImpactReportOut` with populated delta fields
- ImpactReport page renders metric cards with real before/after numbers
- ≥3 metrics show a measurable delta (one of which must be non-zero)
- `coverage_pct` shown as `N/A` if not available — never shown as 0% when the field is `None`

---

## Phase 5 — Integration + Polish + Demo Repo + Docker

**Bob session focus:** End-to-end wiring, demo reliability, and packaging  
**IBM Bob features demonstrated:**
- **Agent mode:** Bob debugs and integrates the full pipeline end-to-end

**Deliverables:**
- `demo/sample_repo/` — engineered Python demo project:
  - ~20 source files in 2–3 modules
  - Deliberate issues: ~30% test coverage, ~10 ruff-fixable lint errors, ~5 undocumented functions, ~8 TODO comments
  - `pyproject.toml` with `[tool.pytest.ini_options]` and `[tool.ruff]` configured
  - Git-tracked so `git checkout .` resets it between demo runs
- Full user workflow functional: repo path input → analysis → missions → execute → verify → impact report
- Navigation between all pages works without state loss
- Error states handled: LLM timeout shows user-facing error; invalid repo path shows validation message
- Loading states: spinner during analysis, skeleton cards during mission load
- `docker-compose.yml` — backend + frontend services; single `docker-compose up` starts the stack
- README updated with Docker and direct-run instructions, verified against a clean environment

**Phase 5 gate (must pass before Phase 6):**
- Full 2.5-minute demo script (from `MVP_SCOPE.md`) runs without errors end-to-end
- No unhandled exceptions in server logs during the demo flow
- All 8 MVP items from `MVP_SCOPE.md` confirmed working
- `docker-compose up` produces a running stack from a clean checkout

---

## Phase 6 — Documentation + Submission

**Bob session focus:** Written submission evidence and final packaging  
**IBM Bob features demonstrated:**
- **Document understanding:** Bob reads all `docs/` planning files to generate coherent submission documents
- **Parallel tasks:** Bob writes `PROBLEM_STATEMENT.md`, `SOLUTION_STATEMENT.md`, and `IBM_BOB_USAGE.md` simultaneously

**Deliverables:**
- `docs/PROBLEM_STATEMENT.md` — required submission document
- `docs/SOLUTION_STATEMENT.md` — required submission document
- `docs/IBM_BOB_USAGE.md` — required submission document (references `bob_sessions/` screenshots)
- `README.md` — polished, demo-ready, setup instructions verified
- `bob_sessions/` — screenshots from all sessions (Phase 0 through Phase 5); each session has start + end screenshot
- Repository pushed public with clean commit history
- Video demo script finalized (follows the 2.5-minute script from `MVP_SCOPE.md`)

**Phase 6 gate (submission ready):**
- All four required written documents present and complete
- `bob_sessions/` contains at least one screenshot per phase (7 sessions)
- README setup instructions produce a running stack on a fresh clone
- Repository is public and accessible

---

## Time Budget (48-hour hackathon)

| Phase | Estimated Hours | Notes |
|---|---|---|
| Phase 0 — Architecture | 2h ✓ | Complete |
| Phase 1 — Foundation | 4h | Parallel Bob tasks keep this short |
| Phase 2 — Analyzer + Missions | 6h | Most LLM prompt engineering here |
| Phase 3 — Orchestrator + Agents + Verification + SSE | 8h | Largest phase; most integration risk |
| Phase 4 — Differ + Impact | 5h | Mostly computation + UI; lower risk |
| Phase 5 — Integration + Demo + Docker | 6h | End-to-end debugging time |
| Phase 6 — Docs + Submission | 4h | Bob parallel tasks accelerate this |
| **Buffer** | **13h** | Absorbs LLM debugging, demo prep, unexpected issues |
| **Total** | **48h** | |

---

## Dependency Order Summary

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
                                 ↑
              VerificationRunner delivered here (with TesterAgent)
              NOT split into Phase 4 — avoids incomplete Phase 3 gate
```

Each phase produces testable, working deliverables. No phase creates components whose dependencies are in a later phase.

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
