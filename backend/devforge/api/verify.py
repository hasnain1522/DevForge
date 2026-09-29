"""Return the verification result generated during a user's mission execution."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from devforge.api.dependencies import get_current_user
from devforge.db.models import ExecutionRun, User, VerificationResult
from devforge.db.session import get_session

router = APIRouter(prefix="/verify", tags=["verify"])


@router.post("/{run_id}")
async def verify_run(
    run_id: str,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict:
    run = session.exec(select(ExecutionRun).where(
        ExecutionRun.id == run_id, ExecutionRun.user_id == user.id,
    )).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    result = session.exec(select(VerificationResult).where(
        VerificationResult.execution_run_id == run_id,
        VerificationResult.user_id == user.id,
    )).first()
    if result is None:
        raise HTTPException(status_code=409, detail="This execution has no verification result")
    return {
        "id": result.id, "execution_run_id": result.execution_run_id,
        "run_at": result.run_at, "passed": result.passed,
        "test_count": result.test_count, "pass_count": result.pass_count,
        "fail_count": result.fail_count, "lint_errors": result.lint_errors,
        "coverage_pct": result.coverage_pct, "raw_output": result.raw_output,
    }
