"""Phase 2 tests for MissionBuilderAgent and mission/analyze API endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from devforge.agents.mission_builder import MissionBuilderAgent, MissionSpec, MissionsResponse
from devforge.db.models import Mission, Repository, RepositorySnapshot
from devforge.db.session import engine, init_db
from devforge.main import app
from devforge.utils.llm import LLMError
from tests.fixtures.fixture_repo import create_fixture_repo

client = TestClient(app)


def _valid_missions_payload(files=None):
    """Return a valid LLM response dict for MissionsResponse."""
    return {
        "missions": [
            {
                "title": "Add tests for auth module",
                "problem": "validate_password has no tests",
                "mission_type": "test_coverage",
                "affected_files": files or ["auth/validators.py"],
                "priority": "high",
                "estimated_effort": "hours",
                "expected_impact": "Increase test coverage",
                "verification_requirements": ["tests pass"],
            },
            {
                "title": "Fix unused imports",
                "problem": "auth/validators.py imports os but never uses it",
                "mission_type": "bug_fix",
                "affected_files": ["auth/validators.py"],
                "priority": "medium",
                "estimated_effort": "minutes",
                "expected_impact": "Clean lint output",
                "verification_requirements": ["ruff clean"],
            },
            {
                "title": "Document helpers module",
                "problem": "utils/helpers.py functions lack docstrings",
                "mission_type": "documentation",
                "affected_files": ["utils/helpers.py"],
                "priority": "low",
                "estimated_effort": "minutes",
                "expected_impact": "Better documentation coverage",
                "verification_requirements": ["docstrings present"],
            },
        ]
    }


# ---------------------------------------------------------------------------
# MissionBuilderAgent unit tests
# ---------------------------------------------------------------------------

class TestMissionBuilderAgent:
    def _make_snapshot(self, **overrides):
        defaults = {
            "file_count": 10,
            "test_file_count": 2,
            "test_function_count": 3,
            "todo_count": 5,
            "lint_error_count": 8,
            "documented_functions_pct": 30.0,
            "languages": '{"python": 10}',
            "top_issues": '["Low test coverage"]',
            "analysis_summary": "A small Python project.",
        }
        defaults.update(overrides)
        return defaults

    @pytest.mark.asyncio
    async def test_generates_missions(self):
        """Agent should return a list of valid mission dicts."""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=MissionsResponse.model_validate(_valid_missions_payload()))

        agent = MissionBuilderAgent(llm=mock_llm)
        result = await agent.run({"snapshot": self._make_snapshot()})

        missions = result["missions"]
        assert len(missions) == 3
        assert missions[0]["mission_type"] in {"test_coverage", "bug_fix", "documentation", "refactor", "dependency_update"}

    @pytest.mark.asyncio
    async def test_sorted_by_priority(self):
        """Missions should be sorted critical > high > medium > low."""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(return_value=MissionsResponse.model_validate(_valid_missions_payload()))

        agent = MissionBuilderAgent(llm=mock_llm)
        result = await agent.run({"snapshot": self._make_snapshot()})

        priorities = [m["priority"] for m in result["missions"]]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        assert priorities == sorted(priorities, key=lambda p: order.get(p, 99))

    @pytest.mark.asyncio
    async def test_llm_failure_raises_llmerror(self):
        """LLM failure must raise LLMError, not return fabricated missions."""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=LLMError("API down"))

        agent = MissionBuilderAgent(llm=mock_llm)
        with pytest.raises(LLMError):
            await agent.run({"snapshot": self._make_snapshot()})

    @pytest.mark.asyncio
    async def test_no_fabricated_missions_on_failure(self):
        """On LLM failure, the result must not contain any missions."""
        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=LLMError("timeout"))

        agent = MissionBuilderAgent(llm=mock_llm)
        try:
            result = await agent.run({"snapshot": self._make_snapshot()})
            # If it doesn't raise, missions must be empty
            assert result.get("missions", []) == []
        except LLMError:
            pass  # This is the expected path

    def test_mission_spec_rejects_empty_affected_files(self):
        """MissionSpec should reject missions with no affected files."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MissionSpec(
                title="Test",
                problem="Problem",
                mission_type="test_coverage",
                affected_files=[],  # empty — should fail
                priority="high",
                estimated_effort="hours",
                expected_impact="impact",
                verification_requirements=[],
            )

    def test_mission_spec_rejects_invalid_type(self):
        """MissionSpec should reject unknown mission_type values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MissionSpec(
                title="Test",
                problem="Problem",
                mission_type="invalid_type",  # not in the allowed set
                affected_files=["foo.py"],
                priority="high",
                estimated_effort="hours",
                expected_impact="impact",
                verification_requirements=[],
            )

    def test_no_estimated_manual_minutes(self):
        """MissionSpec must not have an estimated_manual_minutes field."""
        spec = MissionSpec(
            title="Test",
            problem="Problem",
            mission_type="test_coverage",
            affected_files=["foo.py"],
            priority="high",
            estimated_effort="hours",
            expected_impact="impact",
            verification_requirements=[],
        )
        assert not hasattr(spec, "estimated_manual_minutes")


# ---------------------------------------------------------------------------
# Mission persistence tests
# ---------------------------------------------------------------------------

class TestMissionPersistence:
    def setup_method(self):
        """Ensure tables exist before each test."""
        init_db()

    def test_persist_and_retrieve(self):
        """Missions written to DB should be retrievable by repository_id."""
        with Session(engine) as session:
            repo = Repository(name="test", path="/tmp/persist-test")
            session.add(repo)
            session.commit()
            session.refresh(repo)

            mission = Mission(
                repository_id=repo.id,
                title="Fix lint errors",
                problem="Several ruff violations",
                mission_type="bug_fix",
                affected_files=json.dumps(["auth/validators.py"]),
                priority="medium",
                verification_requirements=json.dumps(["ruff clean"]),
            )
            session.add(mission)
            session.commit()

            results = session.exec(
                select(Mission).where(Mission.repository_id == repo.id)
            ).all()
            assert len(results) >= 1
            assert results[0].mission_type == "bug_fix"
            assert results[0].title == "Fix lint errors"

            # No estimated_manual_minutes column
            assert not hasattr(results[0], "estimated_manual_minutes")

            # Cleanup
            for m in results:
                session.delete(m)
            session.delete(repo)
            session.commit()


# ---------------------------------------------------------------------------
# Analyze API endpoint tests (mock LLM to avoid real API calls)
# ---------------------------------------------------------------------------

class TestAnalyzeAPI:
    def _mock_analyze_and_missions(self, monkeypatch, tmp_path):
        """
        Patch create_llm_client to return a mock that avoids real LLM calls.
        The analyze endpoint calls both RepositoryAnalyzerAgent and MissionBuilderAgent.
        """
        repo = create_fixture_repo(tmp_path)

        # Mock LLM responses
        llm_mock = MagicMock()
        llm_mock.call_json = AsyncMock(side_effect=[
            # First call: RepositoryAnalyzerAgent LLM
            {"top_issues": ["Low test coverage"], "analysis_summary": "Small Python project."},
            # Second call: MissionBuilderAgent LLM
            MissionsResponse.model_validate(_valid_missions_payload()),
        ])

        monkeypatch.setattr(
            "devforge.api.analyze.create_llm_client",
            lambda: llm_mock,
        )
        return repo, llm_mock

    def test_analyze_returns_snapshot(self, monkeypatch, tmp_path):
        """POST /analyze with a valid path should return a RepositorySnapshotOut."""
        repo, _ = self._mock_analyze_and_missions(monkeypatch, tmp_path)

        response = client.post("/analyze", json={"repo_path": str(repo)})
        assert response.status_code == 200, response.text

        data = response.json()
        assert "file_count" in data
        assert "test_file_count" in data
        assert "lint_error_count" in data
        assert "documented_functions_pct" in data
        assert "top_issues" in data
        assert data["snapshot_type"] == "baseline"

    def test_analyze_persists_snapshot(self, monkeypatch, tmp_path):
        """After POST /analyze, a RepositorySnapshot should exist in the DB."""
        repo, _ = self._mock_analyze_and_missions(monkeypatch, tmp_path)

        response = client.post("/analyze", json={"repo_path": str(repo)})
        assert response.status_code == 200

        snapshot_id = response.json()["id"]
        with Session(engine) as session:
            snap = session.get(RepositorySnapshot, snapshot_id)
            assert snap is not None
            assert snap.snapshot_type == "baseline"
            assert snap.file_count >= 1

    def test_analyze_invalid_path_returns_400(self):
        """POST /analyze with a non-existent path should return 400."""
        response = client.post("/analyze", json={"repo_path": "/nonexistent/repo/path"})
        assert response.status_code == 400

    def test_missions_returned_after_analyze(self, monkeypatch, tmp_path):
        """After analysis, GET /missions?repository_id=... should return persisted missions."""
        repo, _ = self._mock_analyze_and_missions(monkeypatch, tmp_path)

        analyze_resp = client.post("/analyze", json={"repo_path": str(repo)})
        assert analyze_resp.status_code == 200

        repo_id = analyze_resp.json()["repository_id"]
        missions_resp = client.get(f"/missions?repository_id={repo_id}")
        assert missions_resp.status_code == 200

        missions = missions_resp.json()
        assert isinstance(missions, list)
        assert len(missions) >= 1

        # Verify mission shape
        m = missions[0]
        assert "title" in m
        assert "mission_type" in m
        assert "priority" in m
        assert "affected_files" in m
        assert isinstance(m["affected_files"], list)
        # No estimated_manual_minutes
        assert "estimated_manual_minutes" not in m

    def test_mission_status_update(self, monkeypatch, tmp_path):
        """PATCH /missions/{id} should update mission status."""
        repo, _ = self._mock_analyze_and_missions(monkeypatch, tmp_path)

        analyze_resp = client.post("/analyze", json={"repo_path": str(repo)})
        assert analyze_resp.status_code == 200

        repo_id = analyze_resp.json()["repository_id"]
        missions_resp = client.get(f"/missions?repository_id={repo_id}")
        missions = missions_resp.json()
        assert len(missions) >= 1

        mission_id = missions[0]["id"]
        patch_resp = client.patch(
            f"/missions/{mission_id}",
            json={"status": "dismissed"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "dismissed"
