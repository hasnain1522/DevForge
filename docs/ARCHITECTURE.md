# DevForge — Architecture Document

**IBM Bob 2.0 Hackathon | September 25–27, 2026**

---

## Overview

DevForge is an agentic AI engineering control center that helps developers manage software-maintenance work as structured **Missions**. A developer points DevForge at a repository; it analyzes the codebase, surfaces prioritized Missions, dispatches specialized Python agents to execute them in parallel, verifies the results, and produces a measurable before/after Impact Report.

> **Important distinction:** DevForge is an independent software product built *using* IBM Bob 2.0 as our AI development partner. DevForge's runtime agents are ordinary Python coroutines — they are not IBM Bob's proprietary runtime and make no claim to reproduce or embed it. IBM Bob usage is documented separately as our development process evidence.

### Core Workflow

```
Repository
    ↓
Repository Analysis
    ↓
Problems / Opportunities Detected
    ↓
Prioritized Missions
    ↓
Agentic Execution  (parallel where safe)
    ↓
Tests / Verification
    ↓
Before vs After Impact Report
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BROWSER UI (React)                   │
│  Dashboard │ Mission Board │ Execution Log │ Impact     │
└────────────────────────┬────────────────────────────────┘
                         │ REST + SSE
┌────────────────────────▼────────────────────────────────┐
│               API SERVER  (FastAPI / Python)             │
│  /analyze  /missions  /execute  /verify  /report        │
└──────┬────────────┬─────────────┬───────────────────────┘
       │            │             │
┌──────▼──┐  ┌──────▼──┐  ┌──────▼──────────────────────┐
│Analyzer │  │ Mission │  │   Agent Orchestrator         │
│ Agent   │  │ Builder │  │  (deterministic parallel     │
└─────────┘  └─────────┘  │   dispatch via templates)   │
                           └────┬──────┬──────┬──────────┘
                                │      │      │
                          ┌─────▼─┐ ┌──▼───┐ ┌▼──────────┐
                          │Impl.  │ │Test  │ │Doc         │
                          │Agent  │ │Agent │ │Agent       │
                          └───────┘ └──────┘ └────────────┘
                                         │
┌────────────────────────────────────────▼────────────────┐
│              VERIFICATION RUNNER  (Python-primary MVP)   │
│  pytest --json-report  │  ruff check  │  grep (generic) │
└─────────────────────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────┐
│              PERSISTENCE  (SQLite via SQLModel)          │
│  repositories │ missions │ execution_runs │ snapshots   │
└─────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Async-native, strong LLM/subprocess support |
| LLM | OpenAI Python SDK (direct) via thin `LLMClient` wrapper | Single dependency, no abstraction library risk; Ollama-compatible via `base_url` override |
| Frontend | React 18 + Vite + TypeScript | Fast dev, type safety, component ecosystem |
| UI Components | Tailwind CSS + shadcn/ui | Zero design time, professional result |
| Persistence | SQLite + SQLModel | Zero-server DB, file-portable |
| Real-time | Server-Sent Events (SSE) | Simple live log streaming |
| Subprocess | Python `subprocess` | Run real linters and test runners |
| Package mgmt | `uv` (Python) + `pnpm` (JS) | Fast installs |

### LLM Provider Strategy

The `LLMClient` wrapper calls `openai.AsyncOpenAI` directly. Provider flexibility is achieved by environment configuration:

```
LLM_API_KEY=sk-...                  # OpenAI or compatible key
LLM_MODEL=gpt-4o-mini               # model name
LLM_BASE_URL=                       # leave empty for OpenAI;
                                    # set to http://localhost:11434/v1 for Ollama
```

No `litellm` or similar translation layer is included in the MVP. If multi-provider support is needed later, `LLMClient` is the only file that changes.

---

## Repository Structure

```
IBM-BOB-2-HACKATHON/
├── bob_sessions/               # IBM Bob session evidence (screenshots)
├── docs/
│   ├── ARCHITECTURE.md         # This document
│   ├── DATA_MODEL.md
│   ├── AGENT_ARCHITECTURE.md
│   ├── IMPLEMENTATION_PHASES.md
│   ├── MVP_SCOPE.md
│   ├── RISKS.md
│   ├── PROBLEM_STATEMENT.md    # (written in Phase 6)
│   ├── SOLUTION_STATEMENT.md   # (written in Phase 6)
│   └── IBM_BOB_USAGE.md        # (written in Phase 6)
├── backend/
│   ├── pyproject.toml
│   ├── devforge/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── api/
│   │   │   ├── analyze.py
│   │   │   ├── missions.py
│   │   │   ├── execute.py
│   │   │   ├── verify.py
│   │   │   └── report.py
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── analyzer.py
│   │   │   ├── mission_builder.py
│   │   │   ├── orchestrator.py
│   │   │   ├── implementer.py
│   │   │   ├── tester.py
│   │   │   └── documenter.py
│   │   ├── verification/
│   │   │   ├── runner.py
│   │   │   ├── python_checks.py      # MVP: pytest + ruff
│   │   │   ├── js_checks.py          # OPTIONAL: vitest + eslint (not MVP)
│   │   │   └── generic_checks.py     # grep-based: TODO/FIXME counts
│   │   ├── snapshot/
│   │   │   └── differ.py
│   │   └── utils/
│   │       ├── file_tree.py
│   │       ├── llm.py                # LLMClient wrapping openai.AsyncOpenAI
│   │       ├── ruff_counter.py       # count_ruff_errors(path) → int
│   │       └── event_bus.py
│   └── tests/
│       ├── fixtures/
│       │   └── sample_repo/          # minimal Python fixture for testing
│       ├── test_analyzer.py
│       ├── test_mission_builder.py
│       └── test_verification.py
├── demo/
│   └── sample_repo/                  # engineered Python demo project
│       └── pyproject.toml            # pytest + ruff configured
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── MissionBoard.tsx
│   │   │   ├── ExecutionView.tsx
│   │   │   └── ImpactReport.tsx
│   │   ├── components/
│   │   │   ├── MissionCard.tsx
│   │   │   ├── AgentLogStream.tsx
│   │   │   ├── MetricDiff.tsx
│   │   │   └── RepoInput.tsx
│   │   ├── api/
│   │   │   └── client.ts
│   │   └── types/
│   │       └── index.ts
│   └── tests/
│       └── MissionCard.test.tsx
├── .env.example
├── docker-compose.yml              # added in Phase 5
└── README.md
```

---

## Module Breakdown

### RepositoryAnalyzerAgent
- Walks directory tree; detects languages; collects file manifest (Python-focused for MVP)
- Reads key manifest files: `README.md`, `pyproject.toml`, `requirements.txt`, `Makefile`
- Computes static metrics using Python AST and subprocess:
  - `test_file_count` — files matching `test_*.py` or `*_test.py`
  - `test_function_count` — AST count of functions named `test_*`
  - `todo_count` — grep for `TODO|FIXME` across source files
  - `lint_error_count` — calls `utils/ruff_counter.py` → `ruff check --output-format=json`
  - `documented_functions_pct` — AST-based docstring presence check (Python only for MVP)
- LLM call → structured JSON: `issues`, `technologies`, `documentation_gaps`, `summary`
- Output: `RepositorySnapshot` persisted to DB

### MissionBuilderAgent
- Input: `RepositorySnapshot`
- LLM call → ranked list of missions (structured JSON, Pydantic-validated)
- Each mission typed as: `bug_fix | test_coverage | documentation | refactor | dependency_update`
- Guardrails: max 10 missions; reject empty `affected_files`; ensure ≥1 `test_coverage` if ratio < 30%
- Output: `Mission[]` persisted to DB

### AgentOrchestrator
- Selects a subtask template based on `mission.mission_type` (deterministic — no LLM call)
- Template maps each mission type to a fixed set of agent assignments with parallel/sequential markers
- Dispatches independent subtasks via `asyncio.gather`
- Dispatches dependent subtasks sequentially after their prerequisites complete
- Holds per-file `asyncio.Lock` to prevent two agents from writing the same file simultaneously
- Streams all events to SSE via EventBus

**Subtask template example — `test_coverage` mission:**
```
Round 1 (parallel via asyncio.gather):
  ImplementerAgent → each file in mission.affected_files
  DocumenterAgent  → each file in mission.affected_files

Round 2 (sequential, waits for Round 1):
  TesterAgent → full suite
```

The template approach eliminates an LLM call from the hot path and ensures deterministic, reliable execution for the demo.

### ImplementerAgent
- Receives file path + instruction from Orchestrator template
- LLM call: existing file content + instruction → targeted code changes (JSON format)
- Applies changes to working copy (not git-staged)
- Emits structured log events per change

### TesterAgent
- Delegates to `VerificationRunner` for the appropriate language
- Parses result into `VerificationResult`
- Emits pass/fail summary event

### DocumenterAgent
- Python AST: identifies functions without docstrings
- LLM call → generates docstrings for undocumented functions
- Applies to file

### VerificationRunner
**MVP (required):**
- Python: `pytest --json-report` + `ruff check --output-format=json`

**Generic (required):**
- grep-based TODO/FIXME counts (language-agnostic)

**Optional (not MVP):**
- JS/TS: vitest + eslint (implemented only if time permits after Phase 5 gate)

### `utils/ruff_counter.py`
Thin utility: `count_ruff_errors(path: str) -> int`
Called by both the Analyzer (to measure the before-baseline) and the VerificationRunner (to measure the after state). These are two separate uses of the same tool — measurement vs. verification — backed by the same function.

### Differ (`snapshot/differ.py`)
- Compares two `RepositorySnapshot` records (before/after)
- Outputs `ImpactReport` with all objective deltas

---

## Agent Parallel Execution Model

```
AgentOrchestrator
│
├── Phase 1 (sequential): AnalyzerAgent
│
├── Phase 2 (sequential): MissionBuilderAgent
│
└── Phase 3 per Mission — driven by static template:
        ┌─── [parallel] ImplementerAgent (file A)
        ├─── [parallel] ImplementerAgent (file B)   ← asyncio.gather
        ├─── [parallel] DocumenterAgent (file A)
        └─── [sequential, waits for all above] TesterAgent
```

Parallelism is always driven by the static template for the mission type, never by an LLM-generated plan. This makes parallel dispatch reliable and predictable.

---

## User Workflow

1. **Load Repository** — Enter local path to a Python repository
2. **Review Analysis** — Dashboard shows file counts, test ratio, lint errors, doc coverage, issues
3. **View Mission Board** — Auto-generated, prioritized, dismissable Missions
4. **Select & Launch Mission** — Live agent log streams execution in real time
5. **Review Results** — Per-file success/failure; changes written to working copy (not auto-committed)
6. **Verify** — Automated pytest + ruff runs; structured pass/fail result shown
7. **Impact Report** — Before/after metric cards; mission marked Completed

---

## Impact Measurement

All metrics listed below are objectively measured from tool output or static analysis. No estimated or LLM-inferred values are presented as measurements.

| Metric | Source | Notes |
|---|---|---|
| Test function count (before/after) | Python AST — count `test_*` functions | Objective |
| Test pass rate (after) | `pytest --json-report` | Objective |
| Lint error count (before/after) | `ruff check --output-format=json` | Objective |
| TODO/FIXME count (before/after) | `grep -rn "TODO\|FIXME"` count | Objective |
| Documented functions % (before/after) | Python AST — docstring presence | Objective; Python-only MVP |
| Lines changed | Character/line diff of modified files | Objective |
| Agent execution time | Wall-clock timing (`time.monotonic`) | Objective |
| Verification passed | Boolean from pytest result | Objective |
| Coverage % | `pytest-cov` output if available | Shown only when tool produces actual output; `None` otherwise |

---

## IBM Bob 2.0 Usage — Build-Time Only

IBM Bob 2.0 is our AI development environment. The table below documents how Bob is used **during development** of DevForge. DevForge's runtime agents are independent Python coroutines; they do not call or embed IBM Bob's runtime.

| IBM Bob Feature | How We Use It to Build DevForge |
|---|---|
| **Agent mode** | Bob builds each backend module autonomously, reading architecture docs before each phase |
| **Parallel tasks** | Bob simultaneously writes multiple agent files in one session (e.g. implementer.py + tester.py + documenter.py) |
| **Subagents** | Bob spawns a subagent to scaffold the React frontend while the main agent builds the backend |
| **Document understanding** | Bob reads ARCHITECTURE.md, DATA_MODEL.md, and AGENT_ARCHITECTURE.md before each implementation phase |

Evidence: `bob_sessions/` directory contains screenshots from each Bob session.

---

## MVP Scope (Must Work in Demo)

1. Analyze a real Python repository and produce a structured snapshot
2. Generate ≥3 missions from analysis
3. Execute one mission end-to-end (test_coverage mission primary demo case)
4. Parallel agent dispatch visible in live log (interleaved SSE events)
5. Verification runner (pytest + ruff) reports pass/fail/count after mission
6. Impact report with ≥3 before/after metric deltas
7. Clean React UI with live agent log stream
8. SQLite persistence (missions and snapshots survive server restart)

---

## Implementation Phases

| Phase | Session | Focus |
|---|---|---|
| 1 | Session 2 | Foundation: FastAPI + DB models + React skeleton |
| 2 | Session 3 | Analyzer + Mission Builder + ruff_counter utility |
| 3 | Session 4 | Orchestrator (templates) + all agents + VerificationRunner core + SSE |
| 4 | Session 5 | Differ + Impact Report computation + Impact Report page |
| 5 | Session 6 | Integration, demo repo engineering, polish, Docker Compose |
| 6 | Session 7 | Submission documents + README + final push |

---

## Judging Criteria Mapping

### Application of Technology
Real LLM orchestration with specialized agents, deterministic parallel dispatch via `asyncio.gather`, Python AST analysis, subprocess verification with real tools (pytest, ruff), SSE real-time streaming, SQLite relational persistence.

### Business Value
Targets software maintenance — one of the highest-cost developer workflows. Measurable ROI via Impact Report: objective numbers from real tool output, not estimates. Reduces context-switching by keeping the entire maintenance workflow in one UI.

### Originality
Mission-based agentic workflow is distinct from "chat with your codebase" tools (Cursor, Copilot). Full closed loop: analysis → parallel execution → verification → quantified impact. Impact Report with before/after proof from real tool output differentiates from pure generation tools.

### Presentation
Live agent log stream with interleaved parallel events makes AI work visible. Large metric cards in Impact Report are immediately legible to non-technical judges. Mission board metaphor is familiar (Kanban). Video script: analyze → missions → launch → watch parallel agents → verification pass → impact numbers.

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
