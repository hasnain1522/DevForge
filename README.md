# ◆ DevForge

> **Agentic AI Engineering Control Center**
>
> Analyze a repository → generate engineering missions → execute scoped agent work → verify with real tools → measure the before/after impact.

DevForge is a full-stack engineering workflow for turning repository findings into **traceable, verifiable engineering work**. Instead of returning only an AI suggestion, DevForge keeps the mission, agent activity, verification output, evidence, snapshots, and polished repository artifact connected to the same execution.

## What DevForge Does

| Stage | What happens |
| --- | --- |
| **1. Analyze** | Inspects a Python repository using objective filesystem, AST, TODO/FIXME, and Ruff metrics. |
| **2. Plan** | Converts findings into scoped engineering missions with affected files and verification requirements. |
| **3. Execute** | Runs the mission through Implementer/Documenter + Tester agents in an isolated workspace. |
| **4. Verify** | Runs command-backed checks such as pytest and Ruff and records the raw verification output. |
| **5. Measure** | Captures before/after repository snapshots and calculates arithmetic impact deltas. |
| **6. Deliver** | Packages the polished repository as a sanitized ZIP and exposes its files for browser preview. |
| **7. Prove** | Persists agent events, verification evidence, file changes, snapshots, and execution logs. |

## Core Product

### 🔎 Repository Analysis
- Python repository structure and language metrics
- Executable test-function detection
- TODO/FIXME detection
- Ruff lint-error measurement
- Production-function documentation coverage
- Mission generation from repository findings

### ⚙️ Agentic Execution
- Mission-scoped affected files
- Isolated per-execution workspace
- Implementer / Documenter agents
- Tester verification
- Retry flow with file checkpoints
- Structured Server-Sent Events for live execution activity

### 🧪 Verification
DevForge treats verification as an engineering gate, not an AI claim.

Typical checks include:

```text
$ python -m pytest -q
.......                                                                  [100%]
7 passed in 0.11s

$ python -m ruff check .
[]
```

The UI preserves the verification result and raw command output for inspection.

### 📊 Impact Reports
Every completed execution can expose:

- tests added
- lint delta
- TODO/FIXME delta
- documentation-coverage delta
- changed files and line counts
- before/after repository snapshots
- execution time
- agent activity
- persisted evidence records

Documentation coverage is measured against **production/source functions**, so adding test files does not artificially dilute the metric.

### 📦 Polished Repository Delivery
A successful execution produces a sanitized ZIP artifact.

The delivery layer:
- excludes Git metadata and generated caches
- excludes common credential files
- redacts detected secret assignments and common token patterns
- provides a browser file preview for text files
- supports direct repository ZIP download

## Architecture

```text
React + Vite + TypeScript
          │
          ▼
      FastAPI API
          │
   ┌──────┼─────────┐
   ▼      ▼         ▼
 Auth   Missions   Execution
                  │
          ┌───────┴────────┐
          ▼                ▼
      Agent Layer       Verification
          │                │
          └───────┬────────┘
                  ▼
          PostgreSQL / SQLite
                  │
                  ▼
       Evidence + Impact Report
```

### Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** FastAPI, SQLModel
- **Database:** PostgreSQL on deployment, SQLite locally
- **Verification:** pytest, Ruff
- **Execution updates:** Server-Sent Events
- **Packaging:** Python ZIP tooling
- **LLM:** backend-configured LLM provider
- **Deployment:** Docker + Render

## Repository Structure

```text
DevForge/
├── backend/
│   ├── devforge/
│   │   ├── agents/          # analyzer, mission builder, implementer, tester
│   │   ├── api/             # auth, analysis, execution, evidence, reports
│   │   ├── db/              # SQLModel tables and sessions
│   │   ├── snapshot/        # objective before/after metrics
│   │   ├── utils/           # repository input, delivery, events, LLM helpers
│   │   └── verification/    # command-backed verification
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/             # typed API client
│       ├── auth/            # session state
│       └── pages/           # dashboard, missions, executions, reports
├── docs/
└── render.yaml
```

## Local Development

### 1. Configure the backend

Copy `.env.example` to `.env` and configure the required backend secrets.

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn devforge.main:app --reload
```

### 2. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, register an account, analyze an accessible Python repository, review the generated missions, and execute one.

### Validation

Backend:

```powershell
cd backend
python -m pytest
python -m ruff check .
```

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Deployment

The production container builds the Vite frontend and serves it through FastAPI alongside the API. Render is configured to deploy from the repository's `main` branch and provision PostgreSQL through the Blueprint configuration.

Live demo:

**https://devforge-xnoz.onrender.com**

## Security Notes

DevForge is designed to avoid exposing repository credentials in generated delivery artifacts. It does not intentionally package `.env` files, common credential files, private-key material, or internal execution directories.

LLM credentials and the authentication signing secret remain backend configuration. Never commit real secrets to the repository.

Repository analysis and agent verification execute tools against the selected repository. Use repositories you are authorized to inspect and modify.

## IBM Bob 2.0 Development Context

IBM Bob 2.0 was used as a development environment during the hackathon build. Bob is **not** a DevForge runtime dependency and is not required to run the application.

Where genuine Bob development evidence is captured, it belongs under `docs/evidence/bob/`.

## Project Status

DevForge is an active hackathon MVP focused on a complete, inspectable engineering loop:

**Analyze → Mission → Execute → Verify → Measure → Deliver → Prove**

The goal is not just to generate code. The goal is to make engineering work **traceable, testable, and measurable**.
