"""List execution runs owned by the authenticated user."""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from devforge.api.dependencies import get_current_user
from devforge.db.models import ExecutionRun, Mission, User
from devforge.db.session import get_session

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("")
async def list_executions(
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict]:
    runs = session.exec(select(ExecutionRun).where(
        ExecutionRun.user_id == user.id,
    ).order_by(ExecutionRun.started_at.desc())).all()
    result = []
    for run in runs:
        mission = session.exec(select(Mission).where(
            Mission.id == run.mission_id, Mission.user_id == user.id,
        )).first()
        result.append({
            "id": run.id, "mission_id": run.mission_id,
            "mission_title": mission.title if mission else "Mission unavailable",
            "status": run.status, "started_at": run.started_at,
            "finished_at": run.finished_at,
        })
    return result
