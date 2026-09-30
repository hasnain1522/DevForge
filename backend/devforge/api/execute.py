"""Start an owned mission, persist its evidence, and stream structured events."""
import asyncio
import difflib
import hashlib
import json
import logging
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from devforge.agents.documenter import DocumenterFailure
from devforge.agents.orchestrator import AgentOrchestrator
from devforge.api.dependencies import get_current_user
from devforge.db.models import (
    ExecutionArtifact,
    ExecutionFailure,
    ExecutionRun,
    ImpactReport,
    Mission,
    Repository,
    RepositorySnapshot,
    SubtaskLog,
    User,
    VerificationResult,
)
from devforge.db.session import engine, get_session
from devforge.snapshot.metrics import capture_metrics
from devforge.utils.delivery import (
    artifact_storage_root,
    create_execution_copy,
    create_repository_zip,
    execution_workspace_path,
)
from devforge.utils.repository_input import RepositoryInputError, resolve_repository_input
from devforge.utils.event_bus import SubtaskLogEvent, event_bus
from devforge.utils.evidence import record_evidence
from devforge.utils.llm import LLMError, create_llm_client
from devforge.verification.runner import VerificationFailure

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execute", tags=["execute"])
_tasks: set[asyncio.Task] = set()


@router.post("/{mission_id}", status_code=202)
async def execute_mission(
    mission_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    mission = session.exec(select(Mission).where(
        Mission.id == mission_id, Mission.user_id == user.id,
    )).first()
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    repo = session.exec(select(Repository).where(
        Repository.id == mission.repository_id, Repository.user_id == user.id,
    )).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if mission.status == "dismissed":
        raise HTTPException(status_code=409, detail="Dismissed missions cannot be executed")

    run = ExecutionRun(mission_id=mission.id, user_id=user.id)
    try:
        if not Path(repo.path).is_dir() and repo.source_url:
            repo.path = str(resolve_repository_input(repo.source_url))
            session.add(repo)
            session.commit()
            session.refresh(repo)
        working_copy = create_execution_copy(repo.path, run.id)
        run.workspace_path = str(working_copy)
        before_metrics = capture_metrics(str(working_copy))
    except (OSError, ValueError, shutil.Error, RepositoryInputError) as exc:
        raise HTTPException(status_code=400, detail="Could not prepare an isolated repository workspace") from exc
    before = RepositorySnapshot(
        user_id=user.id,
        repository_id=repo.id,
        mission_id=mission.id,
        snapshot_type="baseline",
        **before_metrics,
    )
    session.add(before)
    mission.status = "in_progress"
    mission.updated_at = datetime.now(UTC)
    session.add(run)
    # Persist the parent row before creating the FK-dependent artifact.
    # This makes the execution_runs -> execution_artifacts dependency explicit
    # and avoids FK races/order ambiguity across database backends.
    session.flush()
    artifact = ExecutionArtifact(user_id=user.id, execution_run_id=run.id)
    session.add(artifact)
    session.add(mission)
    record_evidence(
        session, user_id=user.id, repository_id=repo.id,
        evidence_type="BEFORE_SNAPSHOT", title="Pre-execution repository snapshot",
        description="Objective repository metrics captured immediately before execution.",
        payload={"snapshot_id": before.id, "metrics": before_metrics},
    )
    session.commit()
    session.refresh(run)
    task = asyncio.create_task(_execute(run.id, mission.id, user.id, str(working_copy), repo.name))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": run.id, "status": run.status}


@router.get("/{run_id}")
async def execution_state(
    run_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    run = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == run_id, ExecutionRun.user_id == user.id,
    )).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    mission = session.exec(select(Mission).where(
        Mission.id == run.mission_id, Mission.user_id == user.id,
    )).first()
    lineage = _execution_lineage(session, run, user.id)
    checkpoints = _execution_checkpoints(session, mission, lineage) if mission else []
    child = session.exec(select(ExecutionRun).where(
        ExecutionRun.parent_execution_run_id == run_id,
        ExecutionRun.user_id == user.id,
    )).first()
    events = session.exec(select(SubtaskLog).where(
        SubtaskLog.execution_run_id == run_id, SubtaskLog.user_id == user.id,
    ).order_by(SubtaskLog.timestamp)).all()
    lineage_ids = [item.id for item in lineage]
    checkpoint_events = session.exec(select(SubtaskLog).where(
        SubtaskLog.execution_run_id.in_(lineage_ids),
        SubtaskLog.user_id == user.id,
    ).order_by(SubtaskLog.timestamp)).all()
    verification = session.exec(select(VerificationResult).where(
        VerificationResult.execution_run_id == run_id,
        VerificationResult.user_id == user.id,
    ).order_by(VerificationResult.run_at.desc())).first()
    failure = session.exec(select(ExecutionFailure).where(
        ExecutionFailure.execution_run_id == run_id,
        ExecutionFailure.user_id == user.id,
    )).first()
    return {
        "id": run.id, "mission_id": run.mission_id, "status": run.status,
        "parent_execution_run_id": run.parent_execution_run_id,
        "retry_available": run.status == "failed" and (child is None or child.status == "running"),
        "retry_run_id": child.id if child and child.status == "running" else None,
        "checkpoints": checkpoints,
        "started_at": run.started_at, "finished_at": run.finished_at,
        "subtask_count": run.subtask_count, "subtasks_completed": run.subtasks_completed,
        "subtasks_failed": run.subtasks_failed,
        "changed_files": sorted({
            e.target_file for e in checkpoint_events if e.target_file
            and e.agent_type in {"implementer", "documenter"}
            and e.event_type in {"completed", "file_retry_completed"}
        }),
        "events": [SubtaskLogEvent(
            execution_run_id=e.execution_run_id, mission_id=run.mission_id,
            user_id=user.id, agent_type=e.agent_type, event_type=e.event_type,
            message=e.message, target_file=e.target_file, timestamp=e.timestamp,
        ).to_sse_dict() for e in events],
        "verification": ({
            "passed": verification.passed, "test_count": verification.test_count,
            "pass_count": verification.pass_count, "fail_count": verification.fail_count,
            "lint_errors": verification.lint_errors, "coverage_pct": verification.coverage_pct,
            "raw_output": verification.raw_output,
        } if verification else None),
        "failure": ({
            "stage": failure.stage, "category": failure.category,
            "reason": failure.reason, "command": failure.command,
            "exit_code": failure.exit_code, "created_at": failure.created_at,
        } if failure else None),
        "artifact": _artifact_out(session.exec(select(ExecutionArtifact).where(
            ExecutionArtifact.execution_run_id == run_id,
            ExecutionArtifact.user_id == user.id,
        )).first()),
    }


@router.get("/{run_id}/artifact")
async def download_execution_artifact(
    run_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    run = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == run_id, ExecutionRun.user_id == user.id,
    )).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    artifact = session.exec(select(ExecutionArtifact).where(
        ExecutionArtifact.execution_run_id == run_id,
        ExecutionArtifact.user_id == user.id,
    )).first()
    if artifact is None or artifact.status != "ready" or not artifact.storage_path or not artifact.filename:
        raise HTTPException(status_code=404, detail="No successful repository artifact is available")
    path = Path(artifact.storage_path).resolve()
    if not path.is_relative_to(artifact_storage_root()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Repository artifact is unavailable")
    return FileResponse(path, media_type="application/zip", filename=artifact.filename)


@router.post("/{run_id}/retry", status_code=202)
async def retry_execution(
    run_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    original = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == run_id, ExecutionRun.user_id == user.id,
    )).first()
    if original is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if original.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed executions can be retried")
    existing = session.exec(select(ExecutionRun).where(
        ExecutionRun.parent_execution_run_id == original.id,
        ExecutionRun.user_id == user.id,
    )).first()
    if existing:
        if existing.status == "running":
            return {"run_id": existing.id, "status": existing.status, "parent_run_id": run_id}
        raise HTTPException(
            status_code=409,
            detail="A retry already exists. Retry the latest failed retry execution instead.",
        )
    mission = session.exec(select(Mission).where(
        Mission.id == original.mission_id, Mission.user_id == user.id,
    )).first()
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    repository = session.exec(select(Repository).where(
        Repository.id == mission.repository_id, Repository.user_id == user.id,
    )).first()
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    lineage = _execution_lineage(session, original, user.id)
    checkpoints = _execution_checkpoints(session, mission, lineage)
    completed_files = [item["filename"] for item in checkpoints if item["status"] == "completed"]
    expected_workspace = execution_workspace_path(original.id)
    source_workspace = Path(original.workspace_path).resolve() if original.workspace_path else expected_workspace
    if source_workspace != expected_workspace or not source_workspace.is_dir():
        raise HTTPException(status_code=409, detail="The failed execution workspace is unavailable for retry")

    retry_run = ExecutionRun(
        mission_id=mission.id, user_id=user.id, parent_execution_run_id=original.id,
        status="running",
    )
    retry_workspace = execution_workspace_path(retry_run.id)
    retry_run.workspace_path = str(retry_workspace)
    session.add(retry_run)
    # Flush the retry parent before inserting its FK-dependent artifact.
    session.flush()
    artifact = ExecutionArtifact(user_id=user.id, execution_run_id=retry_run.id)
    session.add(artifact)
    try:
        # The unique parent link reserves this retry before workspace copying, preventing races.
        session.commit()
        session.refresh(retry_run)
    except IntegrityError as exc:
        session.rollback()
        existing = session.exec(select(ExecutionRun).where(
            ExecutionRun.parent_execution_run_id == original.id,
            ExecutionRun.user_id == user.id,
        )).first()
        if existing and existing.status == "running":
            return {"run_id": existing.id, "status": existing.status, "parent_run_id": run_id}
        raise HTTPException(status_code=409, detail="A retry is already registered for this execution") from exc

    try:
        continuation = create_execution_copy(str(source_workspace), retry_run.id)
        retry_run.workspace_path = str(continuation)
        mission.status = "in_progress"
        mission.updated_at = datetime.now(UTC)
        baseline_metrics = capture_metrics(str(continuation))
        session.add(RepositorySnapshot(
            user_id=user.id, repository_id=mission.repository_id, mission_id=mission.id,
            snapshot_type="baseline", **baseline_metrics,
        ))
        record_evidence(
            session, user_id=user.id, repository_id=mission.repository_id,
            evidence_type="BEFORE_SNAPSHOT", title="Retry continuation snapshot",
            description="Metrics captured from the prior isolated execution workspace before retry.",
            payload={"metrics": baseline_metrics, "parent_execution_id": original.id},
        )
        session.add(retry_run)
        session.add(mission)
        session.commit()
    except Exception as exc:
        session.rollback()
        retry_run = session.exec(select(ExecutionRun).where(ExecutionRun.id == retry_run.id)).first()
        artifact = session.exec(select(ExecutionArtifact).where(
            ExecutionArtifact.execution_run_id == retry_run.id,
        )).first()
        if retry_run:
            retry_run.status = "failed"
            retry_run.finished_at = datetime.now(UTC)
            session.add(retry_run)
            session.add(ExecutionFailure(
                user_id=user.id, execution_run_id=retry_run.id, stage="retry_setup",
                category="continuation_workspace_failed",
                reason="Could not create the isolated continuation workspace.",
            ))
        if artifact:
            artifact.status = "failed"
            session.add(artifact)
        session.commit()
        await event_bus.publish(retry_run.id, SubtaskLogEvent(
            execution_run_id=retry_run.id, mission_id=mission.id, user_id=user.id,
            agent_type="orchestrator", event_type="failed",
            message="Could not create the isolated continuation workspace.",
        ))
        await event_bus.complete(retry_run.id)
        logger.error("Retry workspace preparation failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=409, detail="Could not prepare the retry workspace") from exc

    task = asyncio.create_task(_execute(
        retry_run.id, mission.id, user.id, str(continuation),
        repository.name if repository else "repository",
        resume_completed_files=completed_files, retry_mode=True,
        parent_execution_id=original.id,
    ))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"run_id": retry_run.id, "status": retry_run.status, "parent_run_id": original.id}


def _artifact_out(artifact: ExecutionArtifact | None) -> dict | None:
    if artifact is None:
        return None
    return {
        "execution_id": artifact.execution_run_id,
        "status": artifact.status,
        "filename": artifact.filename,
        "size_bytes": artifact.size_bytes,
        "created_at": artifact.created_at,
    }


def _execution_lineage(session: Session, run: ExecutionRun, user_id: str) -> list[ExecutionRun]:
    lineage = []
    seen = set()
    current = run
    while current and current.id not in seen:
        seen.add(current.id)
        lineage.append(current)
        if not current.parent_execution_run_id:
            break
        current = session.exec(select(ExecutionRun).where(
            ExecutionRun.id == current.parent_execution_run_id,
            ExecutionRun.user_id == user_id,
        )).first()
    return list(reversed(lineage))


def _execution_checkpoints(
    session: Session, mission: Mission, lineage: list[ExecutionRun],
) -> list[dict]:
    filenames = json.loads(mission.affected_files)
    agent = "documenter" if mission.mission_type == "documentation" else "implementer"
    states = {filename: {"status": "not_started", "failure_reason": None,
                         "execution_id": None} for filename in filenames}
    for run in lineage:
        events = session.exec(select(SubtaskLog).where(
            SubtaskLog.execution_run_id == run.id,
            SubtaskLog.agent_type == agent,
            SubtaskLog.target_file.is_not(None),
        ).order_by(SubtaskLog.timestamp, SubtaskLog.id)).all()
        for event in events:
            filename = event.target_file
            if filename not in states:
                continue
            status = {
                "started": "started", "file_retry_started": "started",
                "completed": "completed", "file_retry_completed": "completed",
                "file_skipped": "completed",
                "failed": "failed", "file_retry_failed": "failed",
            }.get(event.event_type)
            if status:
                states[filename] = {
                    "status": status,
                    "failure_reason": event.message if status == "failed" else None,
                    "execution_id": event.execution_run_id,
                }
    return [{"filename": filename, "agent": agent, "order": index,
             "mission_id": mission.id, **states[filename]}
            for index, filename in enumerate(filenames)]


@router.get("/{run_id}/stream")
async def stream_execution(
    run_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
):
    run = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == run_id, ExecutionRun.user_id == user.id,
    )).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    is_finished = run.status != "running"

    async def stream():
        if is_finished:
            with Session(engine) as replay_session:
                events = replay_session.exec(select(SubtaskLog).where(
                    SubtaskLog.execution_run_id == run_id,
                    SubtaskLog.user_id == user.id,
                ).order_by(SubtaskLog.timestamp)).all()
            for item in events:
                yield "data: " + json.dumps(SubtaskLogEvent(
                    execution_run_id=run_id, mission_id=run.mission_id, user_id=user.id,
                    agent_type=item.agent_type, event_type=item.event_type,
                    message=item.message, target_file=item.target_file,
                    timestamp=item.timestamp,
                ).to_sse_dict()) + "\n\n"
        else:
            async for event in event_bus.subscribe(run_id):
                yield f"data: {json.dumps(event.to_sse_dict())}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _execute(
    run_id: str, mission_id: str, user_id: str, repo_path: str, repository_name: str = "repository",
    *, resume_completed_files: list[str] | None = None,
    retry_mode: bool = False, parent_execution_id: str | None = None,
) -> None:
    started = time.monotonic()
    result = None
    error: str | None = None
    failure_data: dict | None = None
    package = None

    async def emit(agent: str, event_type: str, message: str, target_file: str | None = None):
        await event_bus.publish(run_id, SubtaskLogEvent(
            execution_run_id=run_id, mission_id=mission_id, user_id=user_id,
            agent_type=agent, event_type=event_type, message=message, target_file=target_file,
        ))

    try:
        if retry_mode:
            await emit("orchestrator", "retry_started",
                       f"Retry started from execution {parent_execution_id}")
        with Session(engine) as session:
            mission = session.exec(select(Mission).where(
                Mission.id == mission_id, Mission.user_id == user_id,
            )).first()
            if mission is None:
                raise RuntimeError("Mission no longer exists")
            mission_data = {
                "title": mission.title, "problem": mission.problem,
                "mission_type": mission.mission_type,
                "affected_files": json.loads(mission.affected_files),
                "resume_completed_files": resume_completed_files or [],
                "retry_mode": retry_mode,
            }
        result = await AgentOrchestrator(create_llm_client(), emit).run(mission_data, repo_path)
    except DocumenterFailure as exc:
        # DocumenterFailure contains only a filename, fixed category, and safe reason.
        error = str(exc)
        failure_data = {"stage": "documenter", "category": exc.category,
                        "reason": exc.reason, "command": None, "exit_code": None}
    except VerificationFailure as exc:
        failure_data = {"stage": exc.stage, "category": exc.category,
                        "reason": exc.reason, "command": exc.command,
                        "exit_code": exc.exit_code}
        error = _failure_summary(failure_data)
    except LLMError as exc:
        error = _safe_error_detail(exc)
        failure_data = {"stage": "implementer", "category": "provider_error",
                        "reason": error, "command": None, "exit_code": None}
    except Exception as exc:  # noqa: BLE001 - avoid logging sensitive provider exception contents
        logger.error("Execution %s failed (%s): %s", run_id, type(exc).__name__, _safe_error_detail(exc))
        with Session(engine) as session:
            latest = session.exec(select(SubtaskLog).where(
                SubtaskLog.execution_run_id == run_id,
                SubtaskLog.user_id == user_id,
                SubtaskLog.event_type == "started",
            ).order_by(SubtaskLog.timestamp.desc())).first()
        stage = latest.agent_type if latest and latest.agent_type == "tester" else "orchestrator"
        error = f"{stage.capitalize()} failed ({type(exc).__name__}): {_safe_error_detail(exc)}"
        failure_data = {"stage": stage, "category": f"{stage}_error",
                        "reason": error, "command": None, "exit_code": None}

    verification = result["verification"] if result else None
    if result and result.get("failure"):
        failure_data = result["failure"]
        error = _failure_summary(failure_data)
    if verification and not verification["passed"]:
        failure_data = verification.get("failure") or {
            "stage": "verification", "category": "verification_failed",
            "reason": "One or more verification checks failed.",
            "command": None, "exit_code": None,
        }
        error = _failure_summary(failure_data)
    file_changes = result["file_changes"] if result else []
    if retry_mode:
        try:
            with Session(engine) as session:
                mission = session.exec(select(Mission).where(
                    Mission.id == mission_id, Mission.user_id == user_id,
                )).first()
                repository = session.exec(select(Repository).where(
                    Repository.id == mission.repository_id, Repository.user_id == user_id,
                )).first() if mission else None
            if mission and repository:
                parent_workspace = (
                    Path(original.workspace_path).resolve()
                    if original.workspace_path
                    else Path(repository.path).resolve()
                )
                file_changes = _compare_mission_files(
                    str(parent_workspace), repo_path, json.loads(mission.affected_files),
                )
                if result:
                    result["file_changes"] = file_changes
                    result["changed_files"] = [change["path"] for change in file_changes]
        except (OSError, ValueError):
            logger.warning("Could not calculate complete retry file diff for %s", run_id)
    if verification and verification["passed"] and not error:
        try:
            package = create_repository_zip(repo_path, repository_name, run_id)
        except Exception as exc:  # noqa: BLE001 - do not expose filesystem details
            logger.error("Artifact creation failed for execution %s (%s)", run_id, type(exc).__name__)
            error = "Verification passed, but the repository artifact could not be created."

    terminal = "completed" if verification and verification["passed"] and package else "failed"
    if error:
        terminal_message = error
    elif verification and verification["passed"]:
        terminal_message = "Execution, verification, and repository packaging finished"
    else:
        terminal_message = error or "Verification failed"

    try:
        after_metrics = capture_metrics(repo_path)
        with Session(engine) as session:
            run = session.exec(select(ExecutionRun).where(
                ExecutionRun.id == run_id, ExecutionRun.user_id == user_id,
            )).first()
            mission = session.exec(select(Mission).where(
                Mission.id == mission_id, Mission.user_id == user_id,
            )).first()
            artifact = session.exec(select(ExecutionArtifact).where(
                ExecutionArtifact.execution_run_id == run_id,
                ExecutionArtifact.user_id == user_id,
            )).first()
            if run is None or mission is None:
                return
            repository = session.exec(select(Repository).where(
                Repository.id == mission.repository_id, Repository.user_id == user_id,
            )).first()
            before = session.exec(select(RepositorySnapshot).where(
                RepositorySnapshot.mission_id == mission_id,
                RepositorySnapshot.snapshot_type == "baseline",
                RepositorySnapshot.user_id == user_id,
            ).order_by(RepositorySnapshot.taken_at.desc())).first()
            if repository and before:
                after = RepositorySnapshot(
                    user_id=user_id, repository_id=repository.id, mission_id=mission.id,
                    snapshot_type="post_mission", **after_metrics,
                )
                session.add(after)
                session.flush()
                run.status = terminal
                run.subtask_count = result["subtask_count"] if result else 2
                run.subtasks_completed = result["subtasks_completed"] if result else 0
                run.subtasks_failed = result["subtasks_failed"] if result else 1
                run.execution_time_seconds = time.monotonic() - started
                run.finished_at = datetime.now(UTC)
                mission.status = "completed" if terminal == "completed" else "failed"
                mission.updated_at = datetime.now(UTC)
                if verification:
                    verification_fields = {
                        key: verification[key] for key in (
                            "passed", "test_count", "pass_count", "fail_count",
                            "lint_errors", "coverage_pct", "raw_output",
                        )
                    }
                    stored = VerificationResult(
                        user_id=user_id, execution_run_id=run_id, **verification_fields,
                    )
                    session.add(stored)
                    _record_verification_evidence(
                        session, user_id, repository.id, run_id, verification,
                    )
                if failure_data:
                    session.add(ExecutionFailure(
                        user_id=user_id, execution_run_id=run_id,
                        stage=failure_data["stage"], category=failure_data["category"],
                        reason=failure_data["reason"], command=failure_data.get("command"),
                        exit_code=failure_data.get("exit_code"),
                    ))
                lines_changed = sum(
                    change["lines_added"] + change["lines_deleted"] for change in file_changes
                )
                report = ImpactReport(
                    user_id=user_id, mission_id=mission.id, execution_run_id=run.id,
                    before_snapshot_id=before.id, after_snapshot_id=after.id,
                    delta_tests_added=after.test_function_count - before.test_function_count,
                    delta_lint_errors=after.lint_error_count - before.lint_error_count,
                    delta_todo_count=after.todo_count - before.todo_count,
                    delta_doc_coverage_pct=round(
                        after.documented_functions_pct - before.documented_functions_pct, 1,
                    ),
                    lines_changed=lines_changed,
                    agent_execution_time_seconds=run.execution_time_seconds or 0,
                    verification_passed=bool(verification and verification["passed"]),
                )
                session.add(report)
                record_evidence(
                    session, user_id=user_id, repository_id=repository.id,
                    execution_id=run_id, evidence_type="AFTER_SNAPSHOT",
                    title="Post-execution repository snapshot",
                    description="Objective metrics captured after agent execution.",
                    payload={"snapshot_id": after.id, "metrics": after_metrics},
                )
                for change in file_changes:
                    record_evidence(
                        session, user_id=user_id, repository_id=repository.id,
                        execution_id=run_id, evidence_type="FILE_CHANGE",
                        title=f"Changed {change['path']}",
                        description="File content changed by ImplementerAgent or DocumenterAgent.",
                        payload=change,
                    )
                for event in session.exec(select(SubtaskLog).where(
                    SubtaskLog.execution_run_id == run_id,
                    SubtaskLog.user_id == user_id,
                )).all():
                    record_evidence(
                        session, user_id=user_id, repository_id=repository.id,
                        execution_id=run_id, evidence_type="AGENT_ACTION",
                        title=f"{event.agent_type}: {event.event_type}",
                        description=event.message,
                        payload={"target_file": event.target_file, "timestamp": event.timestamp.isoformat()},
                    )
                session.add(run)
                session.add(mission)
                if artifact:
                    artifact.status = "ready" if package and terminal == "completed" else "failed"
                    artifact.filename = package.filename if artifact.status == "ready" else None
                    artifact.size_bytes = package.size_bytes if artifact.status == "ready" else 0
                    artifact.created_at = package.created_at if artifact.status == "ready" else None
                    artifact.storage_path = str(package.path) if artifact.status == "ready" else None
                    session.add(artifact)
                session.commit()
    except Exception as exc:  # noqa: BLE001 - mark run failed even on persistence errors
        logger.error("Execution persistence failed (%s)", type(exc).__name__)
        terminal = "failed"
        terminal_message = "Execution result could not be persisted"
        if package:
            package.path.unlink(missing_ok=True)
        with Session(engine) as session:
            run = session.exec(select(ExecutionRun).where(
                ExecutionRun.id == run_id, ExecutionRun.user_id == user_id,
            )).first()
            if run:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                session.add(run)
            artifact = session.exec(select(ExecutionArtifact).where(
                ExecutionArtifact.execution_run_id == run_id,
                ExecutionArtifact.user_id == user_id,
            )).first()
            if artifact:
                artifact.status = "failed"
                artifact.filename = None
                artifact.size_bytes = 0
                artifact.created_at = None
                artifact.storage_path = None
                session.add(artifact)
            if run:
                session.commit()

    terminal_event = "retry_completed" if retry_mode and terminal == "completed" else terminal
    await emit("orchestrator", terminal_event, terminal_message)
    with Session(engine) as session:
        logs = session.exec(select(SubtaskLog).where(
            SubtaskLog.execution_run_id == run_id, SubtaskLog.user_id == user_id,
        ).order_by(SubtaskLog.timestamp)).all()
        record_evidence(
            session, user_id=user_id, execution_id=run_id,
            evidence_type="EXECUTION_LOG", title="Execution event log",
            description="Persisted structured events emitted during this execution.",
            payload={"events": [{"agent": e.agent_type, "status": e.event_type,
                                  "message": e.message, "timestamp": e.timestamp.isoformat()}
                                 for e in logs]},
        )
        session.commit()
    await event_bus.complete(run_id)


def _record_verification_evidence(
    session: Session, user_id: str, repository_id: str, run_id: str, result: dict,
) -> None:
    raw = result["raw_output"]
    pytest_output = _section(raw, "$ python -m pytest -q\n", "\n$ python -m ruff")
    ruff_output = _section(raw, "$ python -m ruff check .\n", "\n$ TODO/FIXME scan")
    todo_output = raw.split("$ TODO/FIXME scan\n", 1)[-1]
    for evidence_type, title, description, payload in [
        ("TEST_RESULT", "pytest result", "Actual pytest subprocess output.",
         {"pass_count": result["pass_count"], "fail_count": result["fail_count"], "output": pytest_output}),
        ("LINT_RESULT", "ruff result", "Actual ruff subprocess output.",
         {"lint_errors": result["lint_errors"], "output": ruff_output}),
        ("VERIFICATION", "Verification result", "Combined pytest, ruff, and TODO/FIXME outcomes.",
         {"passed": result["passed"], "test_count": result["test_count"],
          "todo_output": todo_output, "coverage_pct": result["coverage_pct"]}),
    ]:
        record_evidence(
            session, user_id=user_id, repository_id=repository_id,
            execution_id=run_id, evidence_type=evidence_type, title=title,
            description=description, payload=payload,
        )


def _section(raw: str, start: str, end: str) -> str:
    content = raw.split(start, 1)[-1]
    return content.split(end, 1)[0] if end in content else content


def _safe_error_detail(exc: Exception) -> str:
    """Keep useful exception detail while removing known credentials and limiting output."""
    from devforge.config import settings

    detail = str(exc) or "No additional error detail was provided."
    for secret in (settings.llm_api_key, settings.openrouter_api_key, settings.auth_secret):
        if secret and secret != "not-configured":
            detail = detail.replace(secret, "[REDACTED]")
    detail = re.sub(
        r"(?i)(sk-[A-Za-z0-9_-]{12,}|Bearer\s+\S+|(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+)",
        "[REDACTED]", detail,
    )
    return detail.replace("\r", " ").replace("\n", " ")[:240]


def _failure_summary(failure: dict) -> str:
    summary = failure["reason"]
    if failure.get("command"):
        summary += f" Check: {failure['command']}"
    if failure.get("exit_code") is not None:
        summary += f" (exit code {failure['exit_code']})"
    return summary + "."


def _compare_mission_files(source_path: str, workspace_path: str, filenames: list[str]) -> list[dict]:
    """Summarize final mission-scoped changes against the untouched registered source."""
    source_root = Path(source_path).resolve()
    workspace_root = Path(workspace_path).resolve()
    changes = []
    for filename in dict.fromkeys(filenames):
        source = (source_root / filename).resolve()
        final = (workspace_root / filename).resolve()
        if not source.is_relative_to(source_root) or not final.is_relative_to(workspace_root):
            continue
        before = source.read_bytes() if source.is_file() else b""
        after = final.read_bytes() if final.is_file() else b""
        if before == after:
            continue
        before_text = before.decode("utf-8", errors="replace")
        after_text = after.decode("utf-8", errors="replace")
        diff = list(difflib.unified_diff(before_text.splitlines(), after_text.splitlines(), lineterm=""))
        changes.append({
            "path": Path(filename).as_posix(),
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "lines_added": sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")),
            "lines_deleted": sum(1 for line in diff if line.startswith("-") and not line.startswith("---")),
        })
    return changes
