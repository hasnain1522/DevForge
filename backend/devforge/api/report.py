"""Return the latest objective impact report for an owned repository."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from devforge.api.dependencies import get_current_user
from devforge.api.schemas import MissionOut, RepositorySnapshotOut
from devforge.db.models import (
    Evidence,
    ExecutionArtifact,
    ExecutionRun,
    ImpactReport,
    Mission,
    Repository,
    RepositorySnapshot,
    SubtaskLog,
    User,
    VerificationResult,
)
from devforge.db.session import get_session

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{repo_id}")
async def get_report(
    repo_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict:
    repository = session.exec(select(Repository).where(
        Repository.id == repo_id, Repository.user_id == user.id,
    )).first()
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    report = session.exec(
        select(ImpactReport)
        .join(Mission, Mission.id == ImpactReport.mission_id)
        .where(Mission.repository_id == repo_id, ImpactReport.user_id == user.id)
        .order_by(ImpactReport.generated_at.desc())
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No impact report is available yet")
    mission = session.get(Mission, report.mission_id)
    run = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == report.execution_run_id, ExecutionRun.user_id == user.id,
    )).first()
    before = session.get(RepositorySnapshot, report.before_snapshot_id)
    after = session.get(RepositorySnapshot, report.after_snapshot_id)
    verification = session.exec(select(VerificationResult).where(
        VerificationResult.execution_run_id == report.execution_run_id,
        VerificationResult.user_id == user.id,
    )).first()
    events = session.exec(select(SubtaskLog).where(
        SubtaskLog.execution_run_id == report.execution_run_id,
        SubtaskLog.user_id == user.id,
    ).order_by(SubtaskLog.timestamp)).all()
    evidence = session.exec(select(Evidence).where(
        Evidence.execution_id == report.execution_run_id,
        Evidence.user_id == user.id,
    ).order_by(Evidence.timestamp)).all()
    if not (mission and run and before and after):
        raise HTTPException(status_code=409, detail="Impact report references incomplete execution data")
    artifact = session.exec(select(ExecutionArtifact).where(
        ExecutionArtifact.execution_run_id == run.id,
        ExecutionArtifact.user_id == user.id,
    )).first()
    return {
        "id": report.id,
        "mission": MissionOut.model_validate(mission).model_dump(mode="json"),
        "execution": {"id": run.id, "status": run.status,
                      "execution_time_seconds": run.execution_time_seconds},
        "artifact": ({
            "execution_id": artifact.execution_run_id,
            "status": artifact.status,
            "filename": artifact.filename,
            "size_bytes": artifact.size_bytes,
            "created_at": artifact.created_at,
        } if artifact else None),
        "verification_passed": report.verification_passed,
        "before_snapshot": RepositorySnapshotOut.model_validate(before).model_dump(mode="json"),
        "after_snapshot": RepositorySnapshotOut.model_validate(after).model_dump(mode="json"),
        "delta_tests_added": report.delta_tests_added,
        "delta_lint_errors": report.delta_lint_errors,
        "delta_todo_count": report.delta_todo_count,
        "delta_doc_coverage_pct": report.delta_doc_coverage_pct,
        "lines_changed": report.lines_changed,
        "agent_execution_time_seconds": report.agent_execution_time_seconds,
        "changed_files": [json.loads(item.payload) for item in evidence if item.evidence_type == "FILE_CHANGE"],
        "verification": ({
            "passed": verification.passed, "test_count": verification.test_count,
            "pass_count": verification.pass_count, "fail_count": verification.fail_count,
            "lint_errors": verification.lint_errors, "coverage_pct": verification.coverage_pct,
            "raw_output": verification.raw_output,
        } if verification else None),
        "agent_actions": [{"agent_type": event.agent_type, "event_type": event.event_type,
                           "message": event.message, "target_file": event.target_file,
                           "timestamp": event.timestamp.isoformat()} for event in events],
        "evidence": [{"id": item.id, "type": item.evidence_type, "title": item.title,
                      "description": item.description, "payload": json.loads(item.payload),
                      "timestamp": item.timestamp.isoformat()} for item in evidence],
    }
