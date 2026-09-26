"""
GET /report/{repo_id} — Phase 4 implementation pending.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{repo_id}")
async def get_report(repo_id: str):
    """
    Return the impact report for a repository.
    Phase 4 implementation pending.
    """
    return {"detail": "Not implemented yet — Phase 4"}
