# DevForge

**Agentic AI Engineering Control Center**

> IBM Bob 2.0 Hackathon — September 25–27, 2026

---

## What is DevForge?

DevForge helps developers manage software-maintenance work as structured **Missions**. Point it at a Python repository and it:

1. **Analyzes** the codebase — detects test coverage gaps, lint errors, and documentation gaps using Python AST and real tool output
2. **Generates Missions** — prioritized, actionable engineering tasks derived from the analysis
3. **Executes Missions** — specialized Python agents (Implementer, Documenter, Tester) work in parallel to address the problems
4. **Verifies results** — runs the real pytest test suite and ruff linter; reports structured pass/fail
5. **Reports impact** — before/after metrics showing measurable, objective improvement

All metrics in the Impact Report come from real tool output — not estimates.

> **Note on IBM Bob:** DevForge is an independent software product built *using* IBM Bob 2.0 as our AI development environment. DevForge's runtime agents are ordinary Python coroutines. They do not call or embed IBM Bob's runtime. See [`docs/IBM_BOB_USAGE.md`](docs/IBM_BOB_USAGE.md) (Phase 6) for development evidence.

---

## Current Status

> **Phase 0 — Architecture approved. Phase 1 implementation pending.**

---

## Documentation

| Document | Description |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full system architecture |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Database schema and API response models |
| [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md) | Agent design, parallel execution model, LLMClient |
| [`docs/IMPLEMENTATION_PHASES.md`](docs/IMPLEMENTATION_PHASES.md) | Build phases, session plan, phase gates |
| [`docs/MVP_SCOPE.md`](docs/MVP_SCOPE.md) | Eight must-have items and demo script |
| [`docs/RISKS.md`](docs/RISKS.md) | Technical and hackathon risks with mitigations |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| LLM | OpenAI Python SDK (direct) via `LLMClient` wrapper |
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Database | SQLite + SQLModel |
| Real-time | Server-Sent Events (SSE) |
| Verification | `pytest` + `ruff` (Python; subprocess) |

**Primary language target:** Python. JS/TS verification is an optional extension, not required for the MVP.

---

## Setup (available after Phase 1)

```bash
# Copy and fill in your LLM API key
cp .env.example .env

# Option A — Docker (added in Phase 5)
docker-compose up

# Option B — Direct
cd backend
uv sync
uv run uvicorn devforge.main:app --reload

cd frontend
pnpm install
pnpm dev
```

---

## IBM Bob 2.0 Usage

DevForge was built using IBM Bob 2.0 as our AI development partner. Bob features used:

| Feature | How We Used It |
|---|---|
| **Agent mode** | Bob built each backend module autonomously, reading architecture docs before each phase |
| **Parallel tasks** | Bob simultaneously wrote multiple agent files per session |
| **Subagents** | Bob spawned a subagent for the React frontend while the main agent built the Python backend |
| **Document understanding** | Bob read all planning documents before each implementation phase |

Session evidence: [`bob_sessions/`](bob_sessions/)

---

## Hackathon

**IBM Bob 2.0 Hackathon** — September 25–27, 2026 — 48-hour build

---

*Built with IBM Bob 2.0*
