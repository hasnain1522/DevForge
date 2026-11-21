# ◆ DevForge

> **AI-Powered Python Repository Analysis & Improvement Platform**
>
> **Inspect → Understand → Prioritize → Fix (with approval) → Verify**

[![Live Demo](https://img.shields.io/badge/Live-Demo-black?style=for-the-badge)](https://devforge-xnoz.onrender.com)

## What is DevForge?

DevForge is an AI-assisted engineering platform built to analyse Python code repositories, surface potential problems and improvement opportunities, explain its findings, and help developers work through selected fixes.

In a small project, a developer can often inspect files manually. In a large repository, understanding how files, modules and tests relate — and finding issues spread across the codebase — can take significant time and effort. Important problems and maintenance opportunities can be easy to overlook.

**That is the problem DevForge was built to address.**

A developer provides a Python repository. DevForge inspects its structure and available engineering signals, presents findings and turns relevant work into scoped missions. The developer can review the proposed work and choose whether to proceed with an AI-assisted implementation. The resulting changes are then checked through configured verification commands, with execution evidence retained for inspection.

DevForge is intended to support the developer, not silently take control of the codebase.

## The Problem We Wanted to Solve

Large Python repositories can contain many modules, dependencies, tests and interconnected workflows. Finding where something is wrong — or where code quality and maintainability can improve — is not always straightforward.

Common challenges include:

- Understanding an unfamiliar or large repository structure
- Finding potential code issues and maintainability concerns
- Locating TODO/FIXME markers and areas that need attention
- Reviewing lint and test signals across multiple files
- Deciding which findings should be addressed first
- Making changes without accidentally breaking existing behaviour
- Checking whether a proposed fix actually passes verification

## How DevForge Works

```text
Connect a Python Repository
          |
          v
   Analyse the Codebase
          |
          v
 Review Findings & Signals
          |
          v
 Prioritise / Create Missions
          |
          v
 User Reviews & Chooses Work
          |
          v
 AI-Assisted Implementation
          |
          v
 Run Verification Checks
          |
          v
 Inspect Changes & Evidence
```

### 1. Analyse

DevForge inspects repository structure and available engineering signals, including Python AST analysis, tests, TODO/FIXME markers and Ruff metrics.

### 2. Understand the Findings

The analysis is used to surface potential problems and improvement areas so the developer has a clearer picture of what may need attention. Findings are signals for review, not a guarantee that every issue has been detected.

### 3. Plan the Work

Relevant findings can be converted into scoped engineering missions rather than asking an agent to make broad, uncontrolled changes across the repository.

### 4. Let the Developer Choose

The developer remains in control of whether to proceed with a proposed mission. DevForge is designed around reviewable, scoped work — not automatic modification without user direction.

### 5. Implement and Verify

The agent workflow can work on a mission in an isolated workspace. DevForge can run configured checks such as pytest and Ruff, then preserve the results and command output for review.

### 6. Review the Evidence

Execution records, events, snapshots and before/after metrics help the developer inspect what happened and what changed.

## Core Capabilities

| Capability | Purpose |
| --- | --- |
| Repository analysis | Inspect Python repository structure and engineering signals |
| AST analysis | Examine Python syntax-tree information |
| Quality signals | Surface TODO/FIXME markers and Ruff metrics |
| Test awareness | Use available tests as part of repository analysis and verification |
| Mission planning | Turn findings into scoped engineering tasks |
| AI-assisted implementation | Work on selected tasks in an isolated workspace |
| Verification | Run configured checks such as pytest and Ruff |
| Evidence and reporting | Preserve execution records, snapshots and before/after metrics |
| Delivery | Prepare a sanitized repository artifact for review |

## What DevForge Is — and Is Not

**DevForge is:**
- A repository analysis and engineering-assistance platform, with a focus on Python projects.
- A way to make codebase findings easier to inspect and prioritise.
- A workflow for turning selected findings into scoped, reviewable engineering work.
- A verification-oriented tool that keeps evidence alongside generated changes.

**DevForge is not:**
- A guarantee that every bug, vulnerability or design flaw will be detected.
- A replacement for developer judgement, code review or security audits.
- A tool that should apply every suggested change without human review.
- A claim that AI-generated code is correct simply because it was generated.

## IBM Bob 2.0 Hackathon

DevForge was developed for the **IBM Bob 2.0 Hackathon**. My participation was **individual (solo) and fully online**. IBM Bob 2.0 was the hackathon development environment and build-time AI coding partner used during development; Bob is not a DevForge runtime dependency.

**Participation format:** Online · Solo participant  
**Project:** DevForge — AI-Powered Python Repository Analysis & Improvement Platform  
**Outcome:** I did not progress as a selected entry. I also did not submit a completed entry: the final end-to-end runtime path was not sufficiently validated before the submission window closed.

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

The official hackathon submission window is now closed. DevForge is preserved as an **honest engineering prototype and portfolio project**, not as a completed competition submission or a finalist project.

> **The decision was not “the project was bad.” The decision was “the evidence was not strong enough to claim what the product promises.”**

That distinction matters.

## Current Limitations

DevForge is an engineering prototype, so it has clear boundaries:

- The real LLM/provider execution path is not fully validated end-to-end.
- Analysis depends on repository structure and the engineering signals available to the system.
- Static analysis and automated checks cannot identify every logical, runtime, security or architectural problem.
- Findings may require developer interpretation and can include false positives or miss issues.
- Agent-generated changes still require human review.
- Verification only covers the checks configured for the project.
- The current system is not yet a production-grade multi-tenant platform.
- Deployment/runtime behaviour can differ from local development environments.
- Impact metrics are only as meaningful as the repository signals and verification commands available to the system.

These limitations are intentionally documented because **verification is the product's core principle**.

## Verification

DevForge treats verification as an engineering gate, not an AI claim.

Typical checks include:

```bash
python -m pytest -q
python -m ruff check .
```

The UI preserves verification results and raw command output for inspection.

## Impact Reports

Completed executions can expose tests added, lint delta, TODO/FIXME delta, documentation-coverage delta, changed files, changed lines, execution time, agent activity, before/after snapshots and persisted evidence.

## Architecture

```text
React + Vite + TypeScript
          |
          v
      FastAPI API
          |
   +------+---------+
   |                |
Repository        Missions
Analysis            |
   |                v
   |          Agent Orchestrator
   |                |
   |          +-----+------+
   |          |            |
   |       Implementer  Tester
   |          |            |
   +----------+------------+
              |
         Verification
              |
       Evidence + Reports
              |
       PostgreSQL / SQLite
```

## Technology Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: Python, FastAPI, SQLModel
- Database: PostgreSQL in deployment / SQLite locally
- Repository analysis: Python AST, repository inspection and Ruff metrics
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

Repository analysis and agent verification should only be used against repositories the operator is authorized to inspect or modify. Review proposed changes before accepting them.

## Current Status

**Hackathon MVP / Engineering Prototype**

## Author

**Mohammed Hasnain**  
CSE AI/ML Student

https://github.com/hasnain1522
