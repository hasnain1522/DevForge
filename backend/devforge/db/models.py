"""
SQLModel database table definitions.

Matches DATA_MODEL.md exactly:
- repositories
- repository_snapshots
- missions
- execution_runs
- subtask_logs
- verification_results
- impact_reports

No estimated_manual_minutes. No source_url. coverage_pct is nullable.
"""
import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Repository(SQLModel, table=True):
    __tablename__ = "repositories"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str
    path: str
    created_at: datetime = Field(default_factory=_now)
    status: str = Field(default="pending")  # pending | analyzing | ready | error


class RepositorySnapshot(SQLModel, table=True):
    __tablename__ = "repository_snapshots"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    repository_id: str = Field(foreign_key="repositories.id")
    taken_at: datetime = Field(default_factory=_now)
    snapshot_type: str  # baseline | post_mission
    mission_id: str | None = Field(default=None, foreign_key="missions.id")

    # Objective metrics — all from static analysis, not LLM estimates
    file_count: int = Field(default=0)
    test_file_count: int = Field(default=0)
    test_function_count: int = Field(default=0)
    todo_count: int = Field(default=0)
    lint_error_count: int = Field(default=0)
    documented_functions_pct: float = Field(default=0.0)

    # JSON-serialised strings
    languages: str = Field(default="{}")        # e.g. '{"python": 12}'
    top_issues: str = Field(default="[]")       # list of issue strings
    analysis_summary: str = Field(default="")


class Mission(SQLModel, table=True):
    __tablename__ = "missions"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    repository_id: str = Field(foreign_key="repositories.id")
    title: str
    problem: str
    mission_type: str  # bug_fix | test_coverage | documentation | refactor | dependency_update
    affected_files: str = Field(default="[]")   # JSON list of file paths
    priority: str = Field(default="medium")     # critical | high | medium | low
    estimated_effort: str = Field(default="hours")   # informational only — LLM text
    expected_impact: str = Field(default="")         # informational only — LLM text
    status: str = Field(default="pending")       # pending | in_progress | completed | failed | dismissed
    verification_requirements: str = Field(default="[]")  # JSON list of checks
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ExecutionRun(SQLModel, table=True):
    __tablename__ = "execution_runs"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    mission_id: str = Field(foreign_key="missions.id")
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = Field(default=None)
    status: str = Field(default="running")  # running | completed | failed
    subtask_count: int = Field(default=0)
    subtasks_completed: int = Field(default=0)
    subtasks_failed: int = Field(default=0)
    execution_time_seconds: float | None = Field(default=None)


class SubtaskLog(SQLModel, table=True):
    __tablename__ = "subtask_logs"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    execution_run_id: str = Field(foreign_key="execution_runs.id")
    agent_type: str  # implementer | tester | documenter | orchestrator
    target_file: str | None = Field(default=None)
    event_type: str  # started | progress | completed | failed
    message: str
    timestamp: datetime = Field(default_factory=_now)


class VerificationResult(SQLModel, table=True):
    __tablename__ = "verification_results"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    execution_run_id: str = Field(foreign_key="execution_runs.id")
    run_at: datetime = Field(default_factory=_now)
    passed: bool = Field(default=False)
    test_count: int = Field(default=0)
    pass_count: int = Field(default=0)
    fail_count: int = Field(default=0)
    lint_errors: int = Field(default=0)
    # coverage_pct is nullable — shown in UI only when pytest-cov produces a real value
    coverage_pct: float | None = Field(default=None)
    raw_output: str = Field(default="")


class ImpactReport(SQLModel, table=True):
    __tablename__ = "impact_reports"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    mission_id: str = Field(foreign_key="missions.id")
    execution_run_id: str = Field(foreign_key="execution_runs.id")
    before_snapshot_id: str = Field(foreign_key="repository_snapshots.id")
    after_snapshot_id: str = Field(foreign_key="repository_snapshots.id")

    # All deltas are arithmetic differences — no LLM estimates
    delta_tests_added: int = Field(default=0)
    delta_lint_errors: int = Field(default=0)    # negative = improvement
    delta_todo_count: int = Field(default=0)     # negative = improvement
    delta_doc_coverage_pct: float = Field(default=0.0)
    lines_changed: int = Field(default=0)
    agent_execution_time_seconds: float = Field(default=0.0)
    verification_passed: bool = Field(default=False)
    generated_at: datetime = Field(default_factory=_now)
