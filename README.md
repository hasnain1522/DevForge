# ◆ DevForge

> **Agentic AI Engineering Control Center**
>
> **Analyze → Mission → Execute → Verify → Measure → Deliver → Prove**

[![Live Demo](https://img.shields.io/badge/Live-Demo-black?style=for-the-badge)](https://devforge-xnoz.onrender.com)

## What is DevForge?

DevForge is a full-stack agentic engineering control center designed to turn repository problems into scoped, executable and verifiable engineering work.

Instead of stopping at an AI suggestion, DevForge connects the complete workflow:

**Analyze → Plan → Execute → Verify → Measure → Deliver → Prove**

## Why I Built It

I wanted to explore a practical question: what would an AI coding workflow look like if it behaved more like an engineering control system than a chatbot?

The core idea is **proof, not just generation**. A useful engineering system should preserve what was found, what was changed, how it was tested, what evidence was produced, and what measurable impact resulted.

## IBM Bob 2.0 Hackathon

DevForge was created as my project for the **IBM Bob 2.0 Hackathon**. IBM Bob 2.0 was used as the development environment during the build; Bob is not a DevForge runtime dependency.

## Why I Did Not Submit a Completed Entry

I chose not to claim a completed submission when the final end-to-end path could not be truthfully validated.

The implementation and engineering validation had progressed substantially, but the configured real LLM provider credential was unavailable for the final end-to-end execution. Because of that, I could not honestly prove the complete live path: real provider response, real agent-driven repository modification, persisted live execution result, live SSE execution, browser-level end-to-end execution, and the final before/after impact report generated from that complete run.

The codebase had already been validated with **43 backend tests, Ruff, frontend typecheck/build, and `git diff --check`**. Those checks were valuable, but they were not a substitute for the missing real-provider execution.

Rather than submit a demo that implied a fully verified runtime path that had not actually been proven, I kept DevForge as an honest, inspectable engineering build. This README intentionally documents that decision.

## AI-Assisted Development

| Contributor / Tool | Role |
| --- | --- |
| **Mohammed Hasnain** | Product owner, architect, decision-maker, integrator, reviewer and final owner |
| **IBM Bob 2.0** | Hackathon development environment and build-time AI coding partner |
| **OpenAI Codex** | Independent validation, debugging and repository-level engineering support |
| **ChatGPT** | Architecture reasoning, debugging, UX planning, documentation and implementation guidance |

These tools helped build and validate the project; they are not DevForge itself.

## Core Product

| Stage | What happens |
| --- | --- |
| Analyze | Inspects repository structure, AST, tests, TODO/FIXME and Ruff metrics |
| Plan | Converts findings into scoped engineering missions |
| Execute | Runs mission-scoped agent work in an isolated workspace |
| Verify | Runs command-backed checks such as pytest and Ruff |
| Measure | Compares objective before/after repository metrics |
| Deliver | Creates a sanitized repository artifact |
| Prove | Preserves events, evidence, snapshots and execution records |

## Verification

DevForge treats verification as an engineering gate, not an AI claim.

Typical checks include:

```text
python -m pytest -q
python -m ruff check .
```

The UI preserves verification results and raw command output for inspection.

## Impact Reports

Completed executions can expose tests added, lint delta, TODO/FIXME delta, documentation-coverage delta, changed files, changed lines, execution time, agent activity, before/after snapshots and persisted evidence.

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

## Technology Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI, SQLModel
- Database: PostgreSQL in deployment / SQLite locally
- Verification: pytest, Ruff
- Streaming: Server-Sent Events
- Packaging: Python ZIP tooling
- Deployment: Docker + Render

## Local Development

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn devforge.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

## Live Demo

https://devforge-xnoz.onrender.com

## Security

Never commit real secrets. Generated delivery artifacts are designed to exclude common credential files, `.env` files, private-key material and internal execution directories.

Repository analysis and agent verification should only be used against repositories the operator is authorized to inspect or modify.

## Current Status

**Hackathon MVP / Engineering Prototype**

## Author

**Mohammed Hasnain**  
CSE AI/ML Student / AI Engineering Developer

https://github.com/hasnain1522