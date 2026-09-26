"""
Missions API — retrieve and update missions for a repository.

GET  /missions?repository_id={id}        — list all missions for a repository
PATCH /missions/{mission_id}             — update mission status
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from devforge.api.schemas import MissionOut
from devforge.db.models import Mission
from devforge.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/missions", tags=["missions"])

VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "failed", "dismissed"})


@router.get("", response_model=list[MissionOut])
async def list_missions(
    repository_id: str,
    session: Session = Depends(get_session),  # noqa: B008
) -> list[MissionOut]:
    """
    Return all missions for the given repository_id, ordered by priority.
    Returns an empty list if the repository has no missions yet.
    """
    stmt = select(Mission).where(Mission.repository_id == repository_id)
    missions = session.exec(stmt).all()

    # Sort by priority: critical → high → medium → low
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    missions_sorted = sorted(missions, key=lambda m: priority_order.get(m.priority, 99))

    return [MissionOut.model_validate(m) for m in missions_sorted]


class MissionStatusUpdate(BaseModel):
    status: str


@router.patch("/{mission_id}", response_model=MissionOut)
async def update_mission_status(
    mission_id: str,
    update: MissionStatusUpdate,
    session: Session = Depends(get_session),  # noqa: B008
) -> MissionOut:
    """
    Update the status of a mission (e.g. dismiss it from the board).
    """
    if update.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Must be one of: {sorted(VALID_STATUSES)}",
        )

    mission = session.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    from datetime import UTC, datetime
    mission.status = update.status
    mission.updated_at = datetime.now(UTC)
    session.add(mission)
    session.commit()
    session.refresh(mission)

    return MissionOut.model_validate(mission)
