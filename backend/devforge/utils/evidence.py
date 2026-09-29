"""Persist evidence derived directly from DevForge database and tool outputs."""
import json

from sqlmodel import Session

from devforge.db.models import Evidence


def record_evidence(
    session: Session,
    *,
    user_id: str,
    evidence_type: str,
    title: str,
    description: str,
    payload: dict,
    execution_id: str | None = None,
    repository_id: str | None = None,
) -> Evidence:
    item = Evidence(
        user_id=user_id,
        execution_id=execution_id,
        repository_id=repository_id,
        evidence_type=evidence_type,
        title=title,
        description=description,
        payload=json.dumps(payload, sort_keys=True, default=str),
    )
    session.add(item)
    return item
