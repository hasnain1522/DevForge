# DevForge

**AI Engineering Control Center** — analyze Python repositories, turn findings into missions, execute scoped agent work, and review command-backed verification and impact.

DevForge provides an authenticated workspace with per-user repository data, mission execution, persisted event/evidence records, and real-time execution updates over Server-Sent Events. Runtime agents use the backend `LLMClient` configured for OpenAI, with optional OpenRouter fallback. IBM Bob was a development tool during earlier implementation; DevForge does not use Bob at runtime or build time.

## Run locally

1. Copy `.env.example` to `.env`; set `LLM_API_KEY` and a random `AUTH_SECRET` of at least 32 characters. OpenRouter is optional.
2. Start the API:

   ```powershell
   cd backend
   python -m pip install -e ".[dev]"
   python -m uvicorn devforge.main:app --reload
   ```

3. In another terminal, start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

Open the Vite URL, register, analyze an accessible local Python repository, review its missions, and start an execution. SQLite is the default database. Treat this MVP as a trusted local environment: repository analysis and verification execute local tools against the selected repository.

## Product flow

- **Analyze:** Python source metrics and prioritized mission generation.
- **Missions:** inspect, dismiss, and execute repository-scoped work.
- **Executions:** follow agent activity and persisted execution state.
- **Evidence and reports:** inspect recorded analysis, file changes, command output, verification, and measured before/after snapshots.

LLM credentials and the session signing secret stay on the backend. `.env` is git-ignored; do not commit it. See [Evidence](docs/EVIDENCE.md), [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), and [Agent Architecture](docs/AGENT_ARCHITECTURE.md).

## Validation

Backend tests live in `backend/tests`. From `backend`, run `python -m pytest` and `python -m ruff check .`. From `frontend`, run `npm run typecheck` and `npm run build`.

## IBM Bob development context

IBM Bob 2.0 was used as a development environment during earlier implementation. It is not a DevForge dependency, runtime provider, or build step. Genuine Bob development records, if available, belong under [`docs/evidence/bob/`](docs/evidence/bob/); none are included unless actually captured.
