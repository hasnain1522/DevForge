"""
POST /analyze — analyze a repository and return a RepositorySnapshot.

Creates a Repository record (or finds existing by path) then runs
RepositoryAnalyzerAgent and MissionBuilderAgent, persisting results to SQLite.
"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from devforge.agents.analyzer import RepositoryAnalyzerAgent
from devforge.agents.mission_builder import MissionBuilderAgent
from devforge.api.schemas import RepositorySnapshotOut
from devforge.db.models import Mission, Repository, RepositorySnapshot
from devforge.db.session import get_session
from devforge.utils.llm import LLMError, create_llm_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    repo_path: str


@router.post("", response_model=RepositorySnapshotOut)
async def analyze_repository(
    request: AnalyzeRequest,
    session: Session = Depends(get_session),  # noqa: B008
) -> RepositorySnapshotOut:
    """
    Analyze a local Python repository.

    1. Validate the path exists on disk.
    2. Create (or reuse) a Repository record.
    3. Run RepositoryAnalyzerAgent → compute objective metrics + LLM summary.
    4. Persist RepositorySnapshot (type=baseline).
    5. Run MissionBuilderAgent → generate and persist Missions.
    6. Return the RepositorySnapshotOut.
    """
    resolved = Path(request.repo_path).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist or is not a directory: {request.repo_path}",
        )

    # ── Find or create Repository record ────────────────────────────────────
    repo_path_str = str(resolved)
    stmt = select(Repository).where(Repository.path == repo_path_str)
    repo = session.exec(stmt).first()

    if repo is None:
        repo = Repository(
            name=resolved.name,
            path=repo_path_str,
            status="analyzing",
        )
        session.add(repo)
        session.commit()
        session.refresh(repo)
    else:
        repo.status = "analyzing"
        session.add(repo)
        session.commit()

    # ── Run analyzer ─────────────────────────────────────────────────────────
    llm = create_llm_client()
    analyzer = RepositoryAnalyzerAgent(llm=llm)

    try:
        metrics = await analyzer.run({"repo_path": repo_path_str})
    except ValueError as exc:
        repo.status = "error"
        session.add(repo)
        session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Analyzer error for %s", repo_path_str)
        repo.status = "error"
        session.add(repo)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    # ── Persist snapshot ─────────────────────────────────────────────────────
    snapshot = RepositorySnapshot(
        repository_id=repo.id,
        snapshot_type="baseline",
        **metrics,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    # ── Generate missions (non-blocking: log failures, don't abort) ──────────
    mission_builder = MissionBuilderAgent(llm=llm)
    try:
        mission_result = await mission_builder.run({"snapshot": metrics})
        _persist_missions(session, repo.id, mission_result["missions"])
    except LLMError as exc:
        logger.warning("Mission generation failed (LLM error): %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mission generation failed: %s", exc)

    # ── Mark repo ready ───────────────────────────────────────────────────────
    repo.status = "ready"
    session.add(repo)
    session.commit()

    return RepositorySnapshotOut.model_validate(snapshot)


def _persist_missions(session: Session, repository_id: str, missions: list[dict]) -> None:
    """Persist the generated mission list to the database."""
    for m in missions:
        mission = Mission(
            repository_id=repository_id,
            title=m["title"],
            problem=m["problem"],
            mission_type=m["mission_type"],
            affected_files=json.dumps(m.get("affected_files", [])),
            priority=m.get("priority", "medium"),
            estimated_effort=m.get("estimated_effort", "hours"),
            expected_impact=m.get("expected_impact", ""),
            status="pending",
            verification_requirements=json.dumps(m.get("verification_requirements", [])),
        )
        session.add(mission)
    session.commit()
    logger.info("Persisted %d missions for repo %s", len(missions), repository_id)
