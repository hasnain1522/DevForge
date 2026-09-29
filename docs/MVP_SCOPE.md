# DevForge — MVP Scope

**IBM Bob 2.0 Hackathon | Phase 0 Planning**

---

> This document describes the original hackathon target. It is not a current completion checklist; see [Implementation status](IMPLEMENTATION_PHASES.md) for shipped scope and known limitations.

## Definition of MVP

The MVP is the minimum set of working features that, together, demonstrate the full DevForge workflow end-to-end and satisfy all four hackathon judging criteria. Every item on this list must work in the live demo.

**Primary language target: Python**  
JS/TS verification is an optional extension — not required for the MVP demo.

---

## Eight MVP Must-Have Items

| # | Feature | Success Criteria | Objective Source |
|---|---|---|---|
| 1 | **Repository Analysis** | Analyze a Python repository; produce a structured snapshot containing: `file_count`, `test_file_count`, `test_function_count`, `todo_count`, `lint_error_count`, `documented_functions_pct`, non-empty `top_issues` | Python AST + `ruff` subprocess + `grep` |
| 2 | **Mission Generation** | ≥3 missions generated from analysis snapshot; persisted to DB; visible on Mission Board with `priority` and `mission_type` badges | LLM structured JSON → Pydantic validation → DB |
| 3 | **Mission Execution** | Execute a `test_coverage` mission; `ImplementerAgent` makes a real code change to ≥1 file; `DocumenterAgent` runs on ≥1 file | File system write confirmed |
| 4 | **Parallel Agents** | ≥2 agent coroutines start before either completes; interleaved SSE events visible in the live log with overlapping timestamps | `asyncio.gather` + SSE event timestamps |
| 5 | **Verification** | After execution, `pytest --json-report` runs against the repo; `VerificationResult` with `test_count`, `pass_count`, `fail_count` returned and displayed | `pytest` subprocess output |
| 6 | **Lint Check** | After execution, `ruff check` runs; `lint_errors` count returned | `ruff check --output-format=json` |
| 7 | **Impact Report** | Before/after values shown for ≥3 metrics; all values derived from objective tool output; no estimated values displayed | Diff of two `RepositorySnapshot` records |
| 8 | **Persistence** | Missions and snapshots are present after server restart; page refresh does not lose state | SQLite confirmed on restart |

---

## Phase 2 Requirement: `utils/ruff_counter.py`

`ruff_counter.py` must be delivered in Phase 2 alongside the Analyzer because:
- `RepositoryAnalyzerAgent` calls `count_ruff_errors()` to populate the **before-baseline** `lint_error_count`
- Without this, `delta_lint_errors` in the Impact Report would be `None` vs. a real number
- The function is a thin `subprocess` wrapper — low implementation risk, high value for the demo

---

## Demo Repository

We need a **controlled demo repository** to guarantee a reliable, predictable demo flow regardless of network conditions or external repositories.

**Location:** `demo/sample_repo/` (inside this repository)

**Language:** Python only (matches MVP verification target)

**Required characteristics:**

| Property | Target | Purpose |
|---|---|---|
| Source files | ~20 `.py` files | Enough to feel real; not so many analysis is slow |
| Modules | 2–3 packages | e.g. `auth/`, `utils/`, `api/` |
| Test files | 4–5 (`test_*.py`) | ~25–30% of source files — below the 30% threshold |
| Test functions | ~10–12 | Low enough that adding 5–8 shows a clear delta |
| Lint errors | ~10 | ruff-fixable (unused imports, missing whitespace, etc.) |
| Undocumented functions | ~8 | Enough for DocumenterAgent to make visible changes |
| TODO comments | ~8 | Spread across multiple files |
| `pyproject.toml` | Present | `[tool.pytest.ini_options]` + `[tool.ruff]` configured |

**Reset strategy:** The demo repo is git-tracked. Running `git checkout demo/sample_repo/` resets it to its original state between demo runs.

---

## Revised Eight MVP Items vs. Architecture Review

The following table confirms that each MVP item maps to an objective, measurable success criterion:

| MVP Item | Metric Used | Is It Objective? |
|---|---|---|
| Repository Analysis | file counts, test counts, lint count, doc % | ✓ All from AST / subprocess |
| Mission Generation | mission count, priority field, type field | ✓ DB records |
| Mission Execution | file modified on disk | ✓ File system |
| Parallel Agents | SSE timestamp overlap | ✓ Wall-clock |
| Verification (pytest) | test_count, pass_count, fail_count | ✓ pytest JSON |
| Lint Check | lint_errors count | ✓ ruff JSON |
| Impact Report | Δ test count, Δ lint errors, Δ doc %, lines changed, execution time | ✓ Arithmetic diff of snapshots |
| Persistence | Data present after restart | ✓ SQLite |

**Removed from MVP:** `estimated_manual_minutes` — this was an LLM estimate, not a measurement. It has been removed from all data models and the Impact Report.

**Conditionally shown:** `coverage_pct` — displayed in the UI only when `pytest-cov` produces a real value. Shown as `N/A` when `None`. Never displayed as `0%` when the field is absent.

---

## Out of Scope for MVP

These items are explicitly excluded. Do not implement until all 8 MVP items are verified at Phase 5 gate.

| Feature | Reason |
|---|---|
| GitHub URL cloning | Adds network/git dependency; demo uses local path |
| JS/TS verification (vitest, eslint) | Python-only MVP; JS/TS adds environment risk |
| `js_checks.py` full implementation | Stub only in Phase 3; optional extension |
| Docker Compose | Phase 5 deliverable; not on MVP critical path |
| Mission dependency graph visualization | UI complexity, low demo value |
| Auto-commit to git branch | Adds risk; changes stay in working copy |
| Multi-repo management | Not needed for demo |
| User authentication | Not needed for hackathon prototype |
| Export to PDF | Low priority |
| Custom mission input (free text) | Nice-to-have; not required |
| Dark mode | Out of scope |
| Go / Rust / Java verification | Out of scope |

---

## Minimum Viable Demo Script

```
00:00  Open DevForge in browser
00:10  Paste path to demo/sample_repo
00:20  Click "Analyze Repository"
00:45  Analysis completes — Dashboard shows:
         20 files  |  10 lint errors  |  34% doc coverage
         10 test functions  |  8 TODOs  |  top issues list
01:00  Navigate to Mission Board
         3+ missions shown with priority badges and mission_type labels
01:15  Click "Execute" on "Improve test coverage for auth module"
01:20  ExecutionView opens — live log begins streaming
01:30  Log shows ImplementerAgent (validators.py) and
         ImplementerAgent (models.py) and DocumenterAgent (validators.py)
         starting with overlapping timestamps — PARALLEL
02:00  TesterAgent runs: "8 passed, 0 failed" in log
02:05  "Mission Complete" banner
02:10  Navigate to Impact Report
02:15  Metric cards show:
         Tests: 10 → 15  (+5)
         Lint errors: 10 → 6  (−4)
         Doc coverage: 34% → 46%  (+12%)
         Lines changed: 87
         Execution time: 42s
02:20  Done
```

Total demo runtime: ~2.5 minutes. Every number on screen comes from a real tool.

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
