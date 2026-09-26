# DevForge — Technical & Hackathon Risks

**IBM Bob 2.0 Hackathon | Phase 0 Planning**

---

## Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **LLM API latency during demo** | Medium | High | Pre-run analysis on demo repo before presentation; results are cached in SQLite. Demo can start from the cached state, skipping the live LLM call for analysis. |
| **LLM produces non-parseable JSON** | Medium | Medium | All LLM calls use `response_format={"type": "json_object"}` (OpenAI SDK). Pydantic validates on every response. `LLMClient.call_json()` retries up to 3 times, feeding the parse error back into the next prompt. Raw output logged for debugging. |
| **ruff not installed on demo machine** | Medium | High | `ruff` is declared as a project dependency in `backend/pyproject.toml`. Running `uv sync` installs it into the project environment. Docker Compose bundles the full environment. This is not an ad-hoc tool — it is an explicit dependency. |
| **pytest not installed on demo machine** | Medium | High | Same mitigation as ruff: `pytest` and `pytest-json-report` are declared in `pyproject.toml`. `uv sync` and Docker both install them. |
| **ImplementerAgent writes syntactically invalid Python** | Medium | Medium | `ImplementerAgent` runs `py_compile.compile()` on the LLM output before writing to disk. If compile fails: log `failed` event, abort the subtask, leave the original file untouched. Other parallel subtasks continue unaffected. |
| **React SSE stream drops on page navigation** | Low | Low | `AgentLogStream` component uses `EventSource` with reconnect on component mount. All events are also persisted to `subtask_logs` in SQLite — full log available via HTTP poll as fallback. |
| **Demo repository analysis too slow** | Low | Medium | Demo repo is ~20 files. Analysis should complete in < 30 seconds. If slower: pre-run analysis before demo and load from cache. File cap of 200 files protects against accidental use of a large repo. |
| **ImplementerAgent makes a breaking change to demo repo** | Low | High | Changes are written to working copy but not committed. The demo repo is git-tracked: `git checkout demo/sample_repo/` resets it instantly. Run this reset between every demo rehearsal. |
| **LLM model unavailable at demo time** | Low | Critical | Configure `LLM_BASE_URL` in `.env` to point to a local Ollama instance as fallback. Single env-var change — no code change required. Test Ollama fallback before presentation day. |

---

## Eliminated Risk: LLM-Generated Orchestration Plan

**Original risk (now eliminated):** The Orchestrator was originally designed to make an LLM call to produce a subtask dependency plan. This introduced a second LLM call in the execution hot path that could fail, return invalid JSON, or produce an incorrect dependency graph (e.g. circular dependencies, missing `TesterAgent`).

**Resolution:** The Orchestrator now uses **static `SUBTASK_TEMPLATES`** keyed on `mission.mission_type`. There is no LLM call during orchestration. The subtask plan is deterministic and tested in unit tests. This risk no longer applies.

---

## Hackathon Execution Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Scope creep kills MVP** | High | Critical | Hard gate: optional features (JS/TS verification, Docker, GitHub cloning) are locked until all 8 MVP items pass Phase 5 gate. Strictly enforce the phase plan. No exceptions. |
| **Phase 3 (agents + SSE + VerificationRunner) underestimated** | Medium | High | Phase 3 has the largest budget (8h) and is the most complex. If running behind: SSE can fall back to HTTP polling without changing the agent architecture. VerificationRunner Python path is the only required implementation. |
| **Demo machine environment issues day-of** | Medium | High | Primary demo: `docker-compose up`. Fallback: `uv run uvicorn` + `pnpm dev` directly. Test both startup paths before presentation day. |
| **IBM Bob session screenshots not captured** | Medium | Medium | Screenshot at the START and END of every Bob session. File naming: `bob_sessions/phase-N-description-start.png` and `-end.png`. One team member assigned as screenshot owner per session. |
| **Written submission documents left to last minute** | Medium | High | Docs written in Phase 6 using IBM Bob's parallel tasks feature — demonstrating Bob while producing required output. Phase 6 is budgeted at 4 hours. |
| **Judging criteria not clearly mapped in demo** | Low | High | Demo script (in `MVP_SCOPE.md`) explicitly narrates the IBM Bob features being demonstrated at each step. `IBM_BOB_USAGE.md` (Phase 6) is thorough with session screenshot references. |
| **Impact Report shows zero deltas (demo repo not exercised enough)** | Low | High | Demo repo is engineered with known, predictable problems. Dry-run the full demo on the demo repo before the hackathon. Confirm ≥3 non-zero deltas appear. Adjust demo repo characteristics if needed. |

---

## Go / No-Go Decision Points

| After Phase | Go-ahead requires |
|---|---|
| Phase 0 | Human architect reviews and approves architecture ✓ |
| Phase 1 | Backend health endpoint returns 200; frontend renders; DB tables created |
| Phase 2 | `/analyze` returns valid snapshot with all required fields; `/missions` returns ≥3 missions; pytest passes |
| Phase 3 | SSE delivers interleaved parallel events to browser; TesterAgent returns real `VerificationResult` from pytest |
| Phase 4 | Impact Report shows ≥3 real before/after deltas; `coverage_pct` shown as `N/A` not `0%` when absent |
| Phase 5 | Full 2.5-minute demo script runs without errors; all 8 MVP items confirmed |

If any phase fails its gate, do not advance. Fix the gate issue first.

---

## Fallback Plans

### LLM completely unavailable
Use pre-recorded fixture JSON for analysis and mission generation. `ImplementerAgent` and `DocumenterAgent` apply hardcoded changes to the demo repo (pre-written, stored as fixtures). Demo flow still demonstrates the full UI and impact report. Narrate that LLM is mocked for demo reliability.

### Docker unavailable on demo machine
Run backend: `uv run uvicorn devforge.main:app --reload`  
Run frontend: `pnpm dev`  
Requires Python 3.11+ and Node 18+ on PATH. Both commands documented in README.

### SSE streaming broken in browser
Agent log shows as a completed result via HTTP poll on `GET /execute/{run_id}/logs`. Visual impact slightly reduced (no live streaming), but the Impact Report is completely unaffected. Narrate "live execution completed" and show the full log.

### ruff or pytest not producing JSON output (version issue)
`ruff_counter.py` and `python_checks.py` both handle subprocess failures by returning 0 / empty results with a logged warning. The demo continues. The affected metrics show `N/A` in the Impact Report rather than crashing.

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
