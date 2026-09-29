# DevForge — Agent Architecture

**IBM Bob 2.0 Hackathon | Phase 0 Planning**

---

> This document captures the original agent design. Current implementation status and limitations are listed in [Implementation status](IMPLEMENTATION_PHASES.md). IBM Bob is development-time context only; it is not a runtime dependency.

## Important Distinction

DevForge's agents are **ordinary Python coroutines** implemented using `asyncio` and the OpenAI Python SDK. They are not IBM Bob subagents, do not call IBM Bob's runtime, and make no claim to reproduce IBM Bob's proprietary capabilities. IBM Bob 2.0 is our **development tool** — we use it to *build* DevForge. That usage is documented in the "IBM Bob Build-Time Usage" section at the end of this document.

---

## Design Principles

1. **Each agent has a single responsibility** — easy to test, explain, and swap
2. **Agents communicate via structured data** — no shared mutable state between agents
3. **Parallelism is explicit and deterministic** — the Orchestrator dispatches from static templates, not LLM-generated plans
4. **LLM calls are isolated in `utils/llm.py`** — retry, JSON validation, and logging centralized in one place
5. **Agents are pure Python classes** — no framework magic, transparent to judges and reviewers

---

## Agent Hierarchy

```
BaseAgent (abstract)
├── RepositoryAnalyzerAgent
├── MissionBuilderAgent
├── AgentOrchestrator
├── ImplementerAgent
├── TesterAgent
└── DocumenterAgent
```

---

## BaseAgent

```python
class BaseAgent:
    name: str              # agent display name for logs
    llm: LLMClient         # injected OpenAI SDK wrapper
    event_bus: EventBus    # for SSE log streaming

    async def run(self, context: dict) -> dict:
        raise NotImplementedError

    async def emit(self, event_type: str, message: str, target_file: str | None = None):
        # writes SubtaskLogEvent to event_bus
        # → stored in subtask_logs table
        # → streamed to browser via SSE
```

All agents receive their dependencies (LLM client, event bus) at construction time.
No global state, no singletons — all dependencies are injected for testability.

---

## RepositoryAnalyzerAgent

**Responsibility:** Understand the repository structure and produce an objective baseline snapshot.

**MVP language scope: Python only**

**Input:**
```python
{
    "repo_path": "/path/to/repo",
    "repository_id": "uuid"
}
```

**Process:**
1. Walk directory tree via `utils/file_tree.py`
   - Skip: `.git`, `__pycache__`, `.venv`, `dist`, `build`, `node_modules`
   - Cap at 200 source files (log a warning if exceeded)
2. Detect Python files by `.py` extension
3. Read key manifest files: `README.md`, `pyproject.toml`, `requirements.txt`, `Makefile`
4. Compute static metrics (no LLM involved at this step):
   - `test_file_count` — files matching `test_*.py` or `*_test.py`
   - `test_function_count` — Python AST count of functions prefixed `test_`
   - `todo_count` — `grep -rn "TODO\|FIXME"` count across `.py` files
   - `lint_error_count` — `utils/ruff_counter.count_ruff_errors(repo_path)` → integer
   - `documented_functions_pct` — Python AST: (functions with docstring / total functions) × 100
5. LLM call (structured JSON output, Pydantic-validated):
   - Input: file tree summary + manifest content + computed metrics
   - Output fields: `issues: list[str]`, `technologies: list[str]`, `documentation_gaps: list[str]`, `summary: str`
6. Persist `RepositorySnapshot` to DB

**Output:**
```python
{
    "snapshot_id": "uuid",
    "file_count": 22,
    "test_file_count": 4,
    "test_function_count": 11,
    "todo_count": 8,
    "lint_error_count": 10,
    "documented_functions_pct": 34.2,
    "languages": {"python": 22},
    "top_issues": ["Low test coverage in auth module", "validate_token undocumented"],
    "analysis_summary": "Small Python service with..."
}
```

---

## MissionBuilderAgent

**Responsibility:** Convert analysis findings into prioritized, actionable Missions.

**Input:** `RepositorySnapshot` dict (from DB or passed directly)

**Process:**
1. Build prompt from snapshot: issues, metrics, file list
2. LLM call → JSON array of missions, Pydantic-validated:
   - Each item: `title`, `problem`, `mission_type`, `affected_files`, `priority`, `estimated_effort`, `expected_impact`, `verification_requirements`
3. Apply guardrails:
   - Maximum 10 missions
   - Reject missions with empty `affected_files`
   - Ensure ≥1 mission of type `test_coverage` when `test_function_count / file_count < 0.3`
4. Sort by priority: `critical > high > medium > low`
5. Persist `Mission[]` to DB

**Output:** `List[Mission]`

Note: `estimated_effort` and `expected_impact` are LLM-generated text for **informational display only**. They are not measurements and are not included in the Impact Report.

---

## AgentOrchestrator

**Responsibility:** Dispatch agents for a selected Mission using deterministic subtask templates.

**Design decision:** The Orchestrator does **not** make an LLM call to plan subtasks. Subtask structure is determined by a static template keyed on `mission.mission_type`. This eliminates a fragile LLM call from the execution hot path and makes parallel dispatch predictable and reliable.

**Input:** `Mission` dict

**Process:**
1. Look up the subtask template for `mission.mission_type`
2. Expand the template: one subtask entry per file in `mission.affected_files` where appropriate
3. Group subtasks into parallel rounds:
   - Round 1: all subtasks with no dependencies → `asyncio.gather`
   - Round 2+: subtasks that depend on Round N completing → `await gather, then dispatch`
4. Before dispatching any subtask to a file, acquire the per-file `asyncio.Lock`
5. Stream all agent events via EventBus to the SSE endpoint

**Subtask templates:**

```python
SUBTASK_TEMPLATES = {
    "test_coverage": [
        # Round 1 — parallel
        {"agent": "implementer", "per_file": True,  "round": 1},
        {"agent": "documenter",  "per_file": True,  "round": 1},
        # Round 2 — sequential, waits for round 1
        {"agent": "tester",      "per_file": False, "round": 2},
    ],
    "documentation": [
        {"agent": "documenter",  "per_file": True,  "round": 1},
        {"agent": "tester",      "per_file": False, "round": 2},
    ],
    "bug_fix": [
        {"agent": "implementer", "per_file": True,  "round": 1},
        {"agent": "tester",      "per_file": False, "round": 2},
    ],
    "refactor": [
        {"agent": "implementer", "per_file": True,  "round": 1},
        {"agent": "documenter",  "per_file": True,  "round": 1},
        {"agent": "tester",      "per_file": False, "round": 2},
    ],
    "dependency_update": [
        {"agent": "implementer", "per_file": True,  "round": 1},
        {"agent": "tester",      "per_file": False, "round": 2},
    ],
}
```

**File locking:**
```python
self._file_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
# Any agent writing to file X must acquire _file_locks[X] first.
# Two agents assigned to the SAME file in the same round
# will serialize automatically via the lock.
```

**Parallel execution for `test_coverage` on 2 files:**
```
Round 1 (asyncio.gather — all start simultaneously):
  ImplementerAgent → auth/validators.py   [lock: validators.py]
  ImplementerAgent → auth/models.py       [lock: models.py]
  DocumenterAgent  → auth/validators.py   ← waits for validators.py lock
  DocumenterAgent  → auth/models.py       ← waits for models.py lock

Round 2 (sequential — waits for Round 1 to complete):
  TesterAgent → runs full pytest suite
```

Interleaved SSE events from Round 1 make parallel execution visually obvious in the demo.

---

## ImplementerAgent

**Responsibility:** Apply a targeted code change to a specific file.

**Input:**
```python
{
    "target_file": "auth/validators.py",
    "instruction": "Add unit tests for validate_email and validate_password",
    "existing_content": "...",     # current file content
    "mission_context": "..."       # mission title + problem description
}
```

**Process:**
1. LLM call with existing content + instruction
   - System prompt specifies: return only the complete updated file content
   - No diff/patch format — full file replacement is simpler and avoids patch-application errors
2. Validate: result is valid Python (compile check via `py_compile.compile`)
3. Write to working copy
4. Emit `progress` event per file

**Safety constraints:**
- Never deletes files
- Never writes paths outside the repo root
- `py_compile` check: if the output is syntactically invalid Python, log `failed` event and abort this subtask (other parallel subtasks continue)

---

## TesterAgent

**Responsibility:** Invoke the VerificationRunner and report structured results.

**Input:**
```python
{
    "repo_path": "/path/to/repo",
    "language": "python"   # determined by Orchestrator from repo snapshot
}
```

**Process:**
1. Call `VerificationRunner.run(repo_path, language="python")`
2. Receive `VerificationResult`
3. Persist to `verification_results` table
4. Emit `completed` event with summary (e.g. "8 passed, 0 failed, 6 lint errors")

**Output:** `VerificationResult`

TesterAgent delegates verification to the implemented `VerificationRunner`; pytest, Ruff, and TODO/FIXME checks run as repository subprocesses.

---

## DocumenterAgent

**Responsibility:** Add missing docstrings to Python functions in a specific file.

**MVP language scope: Python only**

**Input:**
```python
{
    "target_file": "auth/validators.py",
    "existing_content": "..."
}
```

**Process:**
1. Python AST: collect all function definitions (`ast.FunctionDef`, `ast.AsyncFunctionDef`)
2. Identify those without a docstring (first statement is not `ast.Expr(ast.Constant)`)
3. If all functions are documented: emit `completed` with "no changes needed", return
4. LLM call: provide function signatures and bodies → generate docstrings
5. Insert docstrings into the AST output and unparse back to source
6. Write updated file to working copy
7. Emit `completed` event

---

## LLMClient (`utils/llm.py`)

Thin wrapper around `openai.AsyncOpenAI`. All agents call this — never the SDK directly.

```python
import openai
from pydantic import BaseModel

class LLMClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None   # None = OpenAI default; set for Ollama
        )
        self.model = model
        self.max_retries = 3

    async def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel] | None = None
    ) -> dict | BaseModel:
        """
        Call the LLM and return a validated JSON object.
        Retries up to max_retries on JSON parse failure.
        """
        for attempt in range(self.max_retries):
            response = await self._client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ]
            )
            raw = response.choices[0].message.content
            try:
                data = json.loads(raw)
                if response_model:
                    return response_model.model_validate(data)
                return data
            except (json.JSONDecodeError, ValidationError) as e:
                if attempt == self.max_retries - 1:
                    raise
                # feed error back into next attempt
                user_prompt = f"{user_prompt}\n\nPrevious attempt failed: {e}\nPlease correct."

    async def call_text(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM and return raw text (used by ImplementerAgent for full file content)."""
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ]
        )
        return response.choices[0].message.content
```

**Provider configuration (`.env`):**
```
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=              # empty = OpenAI; http://localhost:11434/v1 = Ollama
```

No `litellm` or other abstraction library. If a different provider is needed, only `LLMClient.__init__` changes.

---

## `utils/ruff_counter.py`

```python
def count_ruff_errors(repo_path: str) -> int:
    """
    Run ruff check on repo_path and return the number of errors.
    Returns 0 if ruff is not installed (logs a warning).
    """
```

This function is called by:
- `RepositoryAnalyzerAgent` — to populate `lint_error_count` in the **before** snapshot
- `VerificationRunner.python_checks` — to populate `lint_errors` in `verification_results`

These are two distinct uses (measurement vs. verification) of the same subprocess call.

---

## EventBus (`utils/event_bus.py`)

Connects agents to the SSE endpoint via in-process async queues.

```python
class EventBus:
    _queues: dict[str, asyncio.Queue]   # keyed by execution_run_id

    async def publish(self, run_id: str, event: SubtaskLogEvent) -> None:
        # 1. Persist to subtask_logs table (for replay after page navigation)
        # 2. Put on queue for active SSE subscribers

    async def subscribe(self, run_id: str) -> AsyncIterator[SubtaskLogEvent]:
        # Yield events from queue; used by the SSE endpoint
```

---

## SSE Stream Format

```
GET /execute/{run_id}/stream
Content-Type: text/event-stream

data: {"agent_type":"orchestrator","event_type":"started","message":"Expanding test_coverage template for 2 files...","timestamp":"..."}
data: {"agent_type":"implementer","target_file":"auth/validators.py","event_type":"started","message":"Generating test cases...","timestamp":"..."}
data: {"agent_type":"documenter","target_file":"auth/validators.py","event_type":"started","message":"Reviewing docstrings...","timestamp":"..."}
data: {"agent_type":"implementer","target_file":"auth/models.py","event_type":"started","message":"Generating test cases...","timestamp":"..."}
data: {"agent_type":"implementer","target_file":"auth/validators.py","event_type":"completed","message":"3 test functions added","timestamp":"..."}
data: {"agent_type":"documenter","target_file":"auth/validators.py","event_type":"completed","message":"2 docstrings added","timestamp":"..."}
data: {"agent_type":"implementer","target_file":"auth/models.py","event_type":"completed","message":"2 test functions added","timestamp":"..."}
data: {"agent_type":"orchestrator","event_type":"progress","message":"Round 1 complete. Starting Round 2.","timestamp":"..."}
data: {"agent_type":"tester","event_type":"started","message":"Running pytest...","timestamp":"..."}
data: {"agent_type":"tester","event_type":"completed","message":"8 passed, 0 failed | 6 lint errors","timestamp":"..."}
data: {"event_type":"mission_complete","message":"Mission completed successfully."}
```

Interleaved timestamps from Round 1 make the parallel execution visible and verifiable.

---

## IBM Bob Build-Time Usage

The following table documents how IBM Bob 2.0 is used **during development** to build DevForge. This is entirely separate from DevForge's runtime architecture. DevForge's agents are Python coroutines that have no connection to IBM Bob's runtime.

| IBM Bob Feature | How We Use It to Build DevForge | Build Phase |
|---|---|---|
| **Agent mode** | Bob builds each backend module autonomously, reading architecture and data model docs as context before writing each file | All phases |
| **Parallel tasks** | Bob simultaneously writes `implementer.py`, `tester.py`, and `documenter.py` in a single session | Phase 3 |
| **Parallel tasks** | Bob simultaneously scaffolds `backend/` skeleton and `frontend/` skeleton | Phase 1 |
| **Subagents** | Bob spawns a subagent to build the React frontend while the main agent builds the Python backend | Phase 1 |
| **Document understanding** | Bob reads `ARCHITECTURE.md`, `DATA_MODEL.md`, and `AGENT_ARCHITECTURE.md` before each implementation phase to stay aligned with the plan | All phases |
| **Document understanding** | Bob reads the hackathon brief to produce this architecture | Phase 0 |

Genuine Bob development records, if available, belong under `docs/evidence/bob/`. Their presence is not assumed.

**DevForge analogue (for presentation purposes):**

When presenting DevForge, the following analogy between IBM Bob's build-time role and DevForge's runtime behaviour is useful for storytelling — but must be clearly described as an *analogy*, not a claim that DevForge contains IBM Bob:

| IBM Bob (build-time) | DevForge (runtime) |
|---|---|
| Bob works in Agent mode to autonomously read the codebase and produce code | RepositoryAnalyzerAgent autonomously walks a repo and produces a structured snapshot |
| Bob dispatches parallel tasks across implementer/tester/documenter files | AgentOrchestrator dispatches ImplementerAgent + DocumenterAgent in parallel via `asyncio.gather` |
| Bob spawns subagents for focused work (frontend vs backend) | Orchestrator spawns independent coroutines for each file in the mission |
| Bob reads planning documents before acting | AnalyzerAgent reads README and manifests before calling the LLM |

---

*Document version: Phase 0 rev.1 — Post-review corrections applied*
