"""
POST /analyze — analyze a repository and return a RepositorySnapshot.

Creates a Repository record (or finds existing by path) then runs
RepositoryAnalyzerAgent and MissionBuilderAgent, persisting results to SQLite.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from devforge.agents.analyzer import RepositoryAnalyzerAgent
from devforge.agents.mission_builder import MissionBuilderAgent
from devforge.api.dependencies import get_current_user
from devforge.api.schemas import RepositoryOut, RepositorySnapshotOut
from devforge.db.models import Mission, Repository, RepositorySnapshot, User
from devforge.db.session import get_session
from devforge.utils.evidence import record_evidence
from devforge.utils.llm import LLMError, create_llm_client
from devforge.utils.repository_input import (
    RepositoryInputError,
    canonical_github_url,
    github_origin_from_clone,
    repository_display_name,
    resolve_repository_input,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])
repositories_router = APIRouter(prefix="/repositories", tags=["repositories"])


class AnalyzeRequest(BaseModel):
    repo_path: str


@router.post("", response_model=RepositorySnapshotOut)
async def analyze_repository(
    request: AnalyzeRequest,
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
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
    try:
        resolved = resolve_repository_input(request.repo_path)
    except RepositoryInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Path does not exist or is not a directory, or the GitHub clone is unavailable",
        )

    # ── Find or create Repository record ────────────────────────────────────
    repo = _get_or_create_repository(session, user.id, request.repo_path, resolved)
    repo_path_str = str(resolved)

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
        user_id=user.id,
        repository_id=repo.id,
        snapshot_type="baseline",
        **metrics,
    )
    session.add(snapshot)
    record_evidence(
        session, user_id=user.id, repository_id=repo.id,
        evidence_type="BEFORE_SNAPSHOT", title="Baseline repository snapshot",
        description="Objective baseline metrics captured during repository analysis.",
        payload={"snapshot_id": snapshot.id, "metrics": metrics},
    )
    record_evidence(
        session, user_id=user.id, repository_id=repo.id,
        evidence_type="ANALYSIS", title="Repository analysis completed",
        description="Analysis output persisted from static inspection and tool results.",
        payload={"snapshot_id": snapshot.id},
    )
    session.commit()
    session.refresh(snapshot)

    # ── Generate missions (non-blocking: log failures, don't abort) ──────────
    mission_builder = MissionBuilderAgent(llm=llm)
    try:
        mission_result = await mission_builder.run({"snapshot": metrics})
        _persist_missions(session, repo.id, user.id, mission_result["missions"])
    except LLMError as exc:
        logger.warning("Mission generation failed (LLM error): %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mission generation failed: %s", exc)

    # ── Mark repo ready ───────────────────────────────────────────────────────
    repo.status = "ready"
    session.add(repo)
    session.commit()

    return RepositorySnapshotOut.model_validate(snapshot)


@repositories_router.get("", response_model=list[RepositoryOut])
async def list_repositories(
    session: Session = Depends(get_session),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[RepositoryOut]:
    repos = session.exec(select(Repository).where(Repository.user_id == user.id)).all()
    repaired = False
    for repo in repos:
        if repo.source_url is None and repo.name.lower() == "repository":
            source_url = github_origin_from_clone(repo.path)
            if source_url:
                repo.source_url = source_url
                repo.name = repository_display_name(source_url)
                session.add(repo)
                repaired = True
    if repaired:
        session.commit()
    return [RepositoryOut.model_validate(repo) for repo in repos]


def _persist_missions(
    session: Session, repository_id: str, user_id: str, missions: list[dict],
) -> None:
    """Persist the generated mission list to the database."""
    for m in missions:
        mission = Mission(
            user_id=user_id,
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
        record_evidence(
            session, user_id=user_id, repository_id=repository_id,
            evidence_type="MISSION", title=m["title"],
            description=m["problem"], payload={"mission": m},
        )
    session.commit()
    logger.info("Persisted %d missions for repo %s", len(missions), repository_id)


def _get_or_create_repository(session: Session, user_id: str, source: str, resolved) -> Repository:
    """Reuse a repository identity while refreshing its isolated clone path."""
    repo_path = str(resolved)
    source_url = canonical_github_url(source)
    statement = select(Repository).where(Repository.user_id == user_id)
    statement = statement.where(
        Repository.source_url == source_url if source_url else Repository.path == repo_path
    )
    repository = session.exec(statement).first()
    if repository is None and source_url:
        # Older GitHub records used the fixed clone-folder name and stored only its path.
        candidates = session.exec(select(Repository).where(
            Repository.user_id == user_id,
            Repository.source_url.is_(None),
            Repository.name == "repository",
        )).all()
        repository = next((item for item in candidates
                           if github_origin_from_clone(item.path) == source_url), None)
    if repository is None:
        repository = Repository(
            user_id=user_id, name=repository_display_name(source, resolved), path=repo_path,
            source_url=source_url, status="analyzing",
        )
    else:
        repository.name = repository_display_name(source, resolved)
        repository.path = repo_path
        repository.source_url = source_url
        repository.status = "analyzing"
    session.add(repository)
    session.commit()
    session.refresh(repository)
    return repository
