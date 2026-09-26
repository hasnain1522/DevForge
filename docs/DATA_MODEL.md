# DevForge — Data Model

**IBM Bob 2.0 Hackathon | Phase 0 Planning**

---

## Persistence

SQLite database via SQLModel (Pydantic + SQLAlchemy).
Single file: `devforge.db` in the backend working directory.
No server required. Portable for demo.

---

## MVP Language Scope

All metric computation in `repository_snapshots` is **Python-only for the MVP**. Functions such as `documented_functions_pct`, `test_function_count`, and `lint_error_count` use Python AST and `ruff` respectively. Multi-language computation is an optional extension and is not required for the MVP demo.

---

## Tables

### `repositories`

Stores a registered repository entry.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `name` | str | Display name (derived from path) |
| `path` | str | Local filesystem path |
| `created_at` | datetime | When registered |
| `status` | str | `pending \| analyzing \| ready \| error` |

Note: `source_url` is removed from the MVP schema. GitHub URL cloning is an optional extension. The demo uses a local path only.

---

### `repository_snapshots`

Stores a point-in-time static analysis snapshot of a repository.
Two snapshots per mission (before + after) are the basis for the Impact Report.

All numeric metrics are computed from objective sources: Python AST, `ruff` subprocess output, and `grep`. No values in this table are LLM estimates.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `repository_id` | UUID (FK → repositories) | Parent repository |
| `taken_at` | datetime | Snapshot timestamp |
| `snapshot_type` | str | `baseline \| post_mission` |
| `mission_id` | UUID \| None | Set for `post_mission` snapshots |
| `file_count` | int | Total source files walked |
| `test_file_count` | int | Files matching `test_*.py` or `*_test.py` |
| `test_function_count` | int | Functions named `test_*` found via Python AST |
| `todo_count` | int | TODO + FIXME occurrences (grep count) |
| `lint_error_count` | int | `ruff check` error count (Python only, MVP) |
| `documented_functions_pct` | float | % of Python functions with docstrings (Python AST, MVP) |
| `languages` | JSON str | `{"python": 12}` — extension counts |
| `top_issues` | JSON str | List of issue strings from LLM analysis |
| `analysis_summary` | str | LLM-generated narrative summary |

---

### `missions`

An actionable engineering task derived from repository analysis.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `repository_id` | UUID (FK → repositories) | Parent repository |
| `title` | str | Short mission title |
| `problem` | str | What is wrong / what is missing |
| `mission_type` | str | `bug_fix \| test_coverage \| documentation \| refactor \| dependency_update` |
| `affected_files` | JSON str | List of file paths |
| `priority` | str | `critical \| high \| medium \| low` |
| `estimated_effort` | str | `minutes \| hours \| half_day` (LLM estimate — informational display only, not a measured value) |
| `expected_impact` | str | Short description of expected improvement (LLM-generated, not a measurement) |
| `status` | str | `pending \| in_progress \| completed \| failed \| dismissed` |
| `verification_requirements` | JSON str | List of checks that must pass |
| `created_at` | datetime | When generated |
| `updated_at` | datetime | Last status change |

---

### `execution_runs`

Records one execution of a Mission by the Orchestrator.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `mission_id` | UUID (FK → missions) | Parent mission |
| `started_at` | datetime | Execution start |
| `finished_at` | datetime \| None | Execution end |
| `status` | str | `running \| completed \| failed` |
| `subtask_count` | int | Total subtasks dispatched |
| `subtasks_completed` | int | Successful subtasks |
| `subtasks_failed` | int | Failed subtasks |
| `execution_time_seconds` | float \| None | Wall-clock duration (`time.monotonic`) |

---

### `subtask_logs`

Individual agent log events, streamed via SSE and persisted for replay.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `execution_run_id` | UUID (FK → execution_runs) | Parent run |
| `agent_type` | str | `implementer \| tester \| documenter \| orchestrator` |
| `target_file` | str \| None | File being worked on |
| `event_type` | str | `started \| progress \| completed \| failed` |
| `message` | str | Human-readable log message |
| `timestamp` | datetime | Event time |

---

### `verification_results`

Result of a VerificationRunner pass, linked to an execution run.

All values are taken directly from tool output (`pytest --json-report`, `ruff check --output-format=json`). No values are inferred or estimated.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `execution_run_id` | UUID (FK → execution_runs) | Parent run |
| `run_at` | datetime | When verification ran |
| `passed` | bool | Overall pass/fail (True if all tests pass and lint_errors == 0) |
| `test_count` | int | Total tests discovered by pytest |
| `pass_count` | int | Tests that passed |
| `fail_count` | int | Tests that failed |
| `lint_errors` | int | `ruff check` error count post-execution |
| `coverage_pct` | float \| None | Line coverage % — populated only when `pytest-cov` is installed and produces output; `None` otherwise. Never shown in UI unless a real value is present. |
| `raw_output` | str | Full tool stdout/stderr for debugging |

---

### `impact_reports`

Computed before/after comparison for a completed mission. All delta values are the arithmetic difference between two `repository_snapshots` records. No LLM-inferred values are stored here.

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique identifier |
| `mission_id` | UUID (FK → missions) | Parent mission |
| `execution_run_id` | UUID (FK → execution_runs) | Producing run |
| `before_snapshot_id` | UUID (FK → repository_snapshots) | Pre-execution snapshot |
| `after_snapshot_id` | UUID (FK → repository_snapshots) | Post-execution snapshot |
| `delta_tests_added` | int | `after.test_function_count − before.test_function_count` |
| `delta_lint_errors` | int | `after.lint_error_count − before.lint_error_count` (negative = improvement) |
| `delta_todo_count` | int | `after.todo_count − before.todo_count` (negative = improvement) |
| `delta_doc_coverage_pct` | float | `after.documented_functions_pct − before.documented_functions_pct` |
| `lines_changed` | int | Total lines modified across all files touched by agents |
| `agent_execution_time_seconds` | float | Wall-clock duration of the execution run |
| `verification_passed` | bool | From `verification_results.passed` |
| `generated_at` | datetime | Report generation time |

**Removed field:** `estimated_manual_minutes` — this was an LLM estimate presented alongside objective measurements. It has been removed. If effort context is needed for the presentation, it belongs in narration, not in a data record.

---

## Entity Relationships

```
repositories
    │
    ├── repository_snapshots (1:N)
    │       baseline + post_mission
    │
    └── missions (1:N)
            │
            └── execution_runs (1:N)
                    │
                    ├── subtask_logs (1:N)
                    │
                    ├── verification_results (1:1)
                    │
                    └── impact_reports (1:1)
                            ├── FK → before_snapshot
                            └── FK → after_snapshot
```

---

## Pydantic Response Models (API layer)

These are separate from DB models and used for API serialization. All fields are from objective data sources unless explicitly noted as LLM-generated informational text.

### `RepositoryOut`
```python
id, name, path, status, created_at
```

### `RepositorySnapshotOut`
```python
id, repository_id, taken_at, snapshot_type,
file_count, test_file_count, test_function_count,
todo_count, lint_error_count, documented_functions_pct,
languages, top_issues, analysis_summary
```

### `MissionOut`
```python
id, repository_id, title, problem, mission_type,
affected_files, priority, estimated_effort,   # informational only
expected_impact,                               # informational only
status, verification_requirements,
created_at, updated_at
```

### `ExecutionRunOut`
```python
id, mission_id, started_at, finished_at, status,
subtask_count, subtasks_completed, subtasks_failed,
execution_time_seconds
```

### `VerificationResultOut`
```python
id, execution_run_id, run_at, passed,
test_count, pass_count, fail_count,
lint_errors,
coverage_pct  # None if not available
```

### `ImpactReportOut`
```python
mission_id,
delta_tests_added,       # objective
delta_lint_errors,       # objective
delta_todo_count,        # objective
delta_doc_coverage_pct,  # objective (Python only)
lines_changed,           # objective
agent_execution_time_seconds,  # objective
verification_passed,     # objective
before_snapshot: RepositorySnapshotOut,
after_snapshot: RepositorySnapshotOut
```

### `SubtaskLogEvent` (SSE payload)
```python
execution_run_id, agent_type, target_file,
event_type, message, timestamp
```

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
