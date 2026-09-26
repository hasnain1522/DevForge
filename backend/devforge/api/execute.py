"""
POST /execute/{mission_id} — Phase 3 implementation pending.
GET  /execute/{run_id}/stream — Phase 3 SSE implementation pending.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/execute", tags=["execute"])


@router.post("/{mission_id}")
async def execute_mission(mission_id: str):
    """
    Execute a mission via the AgentOrchestrator.
    Phase 3 implementation pending.
    """
    return {"detail": "Not implemented yet — Phase 3"}


@router.get("/{run_id}/stream")
async def stream_execution(run_id: str):
    """
    SSE stream for live agent execution events.
    Phase 3 implementation pending.
    """
    return {"detail": "Not implemented yet — Phase 3"}
