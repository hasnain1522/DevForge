"""List evidence records owned by the authenticated user."""
import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from devforge.api.dependencies import get_current_user
from devforge.db.models import Evidence, User
from devforge.db.session import get_session

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("")
async def list_evidence(
    repository_id: str | None = None,
    execution_id: str | None = None,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[dict]:
    query = select(Evidence).where(Evidence.user_id == user.id)
    if repository_id:
        query = query.where(Evidence.repository_id == repository_id)
    if execution_id:
        query = query.where(Evidence.execution_id == execution_id)
    items = session.exec(query.order_by(Evidence.timestamp.desc())).all()
    return [{
        "id": item.id, "user_id": item.user_id, "execution_id": item.execution_id,
        "repository_id": item.repository_id, "type": item.evidence_type,
        "title": item.title, "description": item.description,
        "payload": json.loads(item.payload), "timestamp": item.timestamp,
    } for item in items]
