# DevForge — LinkedIn Post

🚀 I built **DevForge — an Agentic AI Engineering Control Center**.

The idea was simple:

**AI should not just change your code. It should help you prove the change.**

DevForge turns a repository problem into a traceable engineering workflow:

🔎 Analyze a repository  
🎯 Generate engineering missions  
🤖 Execute scoped agent work  
🧪 Verify with real tools  
📊 Measure before/after impact  
📦 Deliver a polished repository  
🧾 Preserve evidence of the execution

The system connects mission definitions, affected files, agent activity, pytest/Ruff verification, repository snapshots, file-level changes, impact metrics, evidence records, execution logs, and a downloadable polished repository artifact.

### How the AI tools were used

This project was not built by pretending one AI did everything.

- **Mohammed Hasnain:** product owner, architect, decision-maker, integrator, reviewer, and final owner of what was implemented and claimed.
- **IBM Bob 2.0:** the primary hackathon development environment and build-time AI coding partner. Bob was used for the actual hackathon development workflow, agent-mode work, parallel/sub-agent tasks, document understanding, and development evidence captured in bob_sessions.
- **OpenAI Codex:** engineering validation and debugging layer. It was used to inspect the repository, run validation, identify defects, fix integration issues, and validate backend/frontend quality gates.
- **ChatGPT:** architecture and reasoning partner. It was used for system design, implementation planning, debugging, UX/report design, documentation, and turning requirements and failures into concrete engineering tasks.

The tools had different jobs, but **the human remained responsible for the product decisions and final review**.

### Why I did not submit it as a completed hackathon entry

I chose not to submit a project that I could not honestly say was fully validated.

The final end-to-end run required a working LLM provider configuration. The credentials were unavailable, so although the engineering foundation was substantially implemented, I could not truthfully verify the complete live path: real provider response → real agent file modification → persistence → SSE execution stream → browser execution → final before/after impact report.

Codex had already validated **43 backend tests, Ruff, frontend typecheck/build, and git diff --check**, but those checks were not a substitute for the missing real-provider execution.

So I kept the project honest instead of presenting an unverified end-to-end claim.

That decision also became part of the engineering story: **verification is a feature, not a marketing sentence.**

### Stack

React + TypeScript + Vite  
FastAPI + Python  
SQLModel + PostgreSQL / SQLite  
pytest + Ruff  
Server-Sent Events  
LLM agents  
Docker + Render

🔗 Live Demo: https://devforge-xnoz.onrender.com  
🔗 GitHub: https://github.com/hasnain1522/DevForge

#AI #AgenticAI #ArtificialIntelligence #SoftwareEngineering #DeveloperTools #Python #FastAPI #React #TypeScript #Hackathon #IBM #GitHub #DevTools
