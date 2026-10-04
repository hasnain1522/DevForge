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

DevForge was created as my project for the **IBM Bob 2.0 Hackathon**. IBM Bob 2.0 was the hackathon development environment and build-time AI coding partner used during development; Bob is not a DevForge runtime dependency.

The hackathon submission requirements included a public code repository, demo application, video, presentation, written problem/solution and IBM Bob usage statements, plus evidence of Bob-assisted work such as task-session summary screenshots. DevForge's development process is documented here transparently rather than presenting AI assistance as hidden or manual work.

## AI-Assisted Development

| Contributor / Tool | Role |
| --- | --- |
| **Mohammed Hasnain** | Product owner, architect, decision-maker, integrator, reviewer and final owner |
| **IBM Bob 2.0** | Hackathon development environment and build-time AI coding partner |
| **OpenAI Codex** | Independent validation, debugging and repository-level engineering support |
| **ChatGPT** | Architecture reasoning, debugging, UX planning, documentation and implementation guidance |

These tools supported development; they are not DevForge itself. The product concept, architecture decisions, integration, implementation direction, testing decisions and final ownership remained with me.

## Why I Did Not Submit a Completed Entry

DevForge was built for the **IBM Bob 2.0 Hackathon**, but I did not submit it as a completed entry because the final end-to-end runtime path was not sufficiently validated before the submission window closed.

During the hackathon period, I was also involved in an **accident**, which reduced my available development time and contributed to the missed submission timeline.

The implementation was substantially built and locally validated, but the configured real LLM provider credential was unavailable for the final live execution. That meant I could not honestly demonstrate the complete chain of **real provider response → agent-driven repository change → persisted execution result → live SSE execution → browser-level end-to-end flow → final before/after impact report**.

I could have submitted a polished-looking demo anyway. I chose not to. For an engineering project whose central promise is **verification and evidence**, claiming a fully verified runtime without proving that path would have contradicted the product itself.

The official hackathon submission window is now closed, so this repository is preserved as an **honest engineering prototype and portfolio project**, rather than being presented as a completed competition submission.

> **The decision was not “the project was bad.” The decision was “the evidence was not strong enough to claim what the product promises.”**

That distinction matters.

## Current Limitations

DevForge is an engineering prototype, so it has clear boundaries:

- The real LLM/provider execution path is not fully validated end-to-end.
- Agent-generated changes still require human review.
- Repository analysis depends on the project's structure and available engineering signals.
- Verification only covers the checks configured for the project.
- The current system is not yet a production-grade multi-tenant platform.
- Deployment/runtime behavior can differ from local development environments.
- Impact metrics are only as meaningful as the repository signals and verification commands available to the system.

These limitations are intentionally documented because **verification is the product's core principle**.

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