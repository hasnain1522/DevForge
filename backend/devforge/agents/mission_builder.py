"""
MissionBuilderAgent — converts a RepositorySnapshot into prioritized engineering Missions.
"""
import json
import logging
from pathlib import Path

from pydantic import BaseModel, field_validator

from devforge.agents.base import BaseAgent
from devforge.utils.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)

VALID_MISSION_TYPES = frozenset({
    "bug_fix", "test_coverage", "documentation", "refactor", "dependency_update"
})
VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
VALID_EFFORTS = frozenset({"minutes", "hours", "half_day"})


class MissionSpec(BaseModel):
    """Schema for a single mission returned by the LLM."""
    title: str
    problem: str
    mission_type: str
    affected_files: list[str]
    priority: str
    estimated_effort: str
    expected_impact: str
    verification_requirements: list[str]

    @field_validator("mission_type")
    @classmethod
    def validate_mission_type(cls, v: str) -> str:
        if v not in VALID_MISSION_TYPES:
            raise ValueError(f"mission_type must be one of {VALID_MISSION_TYPES}, got '{v}'")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        return v if v in VALID_PRIORITIES else "medium"

    @field_validator("estimated_effort")
    @classmethod
    def validate_effort(cls, v: str) -> str:
        return v if v in VALID_EFFORTS else "hours"

    @field_validator("affected_files")
    @classmethod
    def validate_affected_files(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("affected_files must not be empty")
        return v


class MissionsResponse(BaseModel):
    """Top-level wrapper expected from the LLM."""
    missions: list[MissionSpec]


_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class MissionBuilderAgent(BaseAgent):
    """Generates prioritized engineering Missions from a RepositorySnapshot."""

    name = "mission_builder"

    def __init__(self, llm: LLMClient) -> None:
        super().__init__()
        self.llm = llm

    async def run(self, context: dict) -> dict:
        """Generate missions from the snapshot in context['snapshot'].""" 
        snapshot = context.get("snapshot")
        if not snapshot:
            raise ValueError("context must contain 'snapshot'")

        missions_raw = await self._generate(snapshot)
        missions_raw.sort(key=lambda m: _PRIORITY_ORDER.get(m["priority"], 99))
        return {"missions": missions_raw}

    async def _generate(self, snapshot: dict) -> list[dict]:
        """Call the LLM, validate missions, and normalize test-coverage targets."""
        try:
            result = await self.llm.call_json(
                self._build_system_prompt(),
                self._build_user_prompt(snapshot),
                response_model=MissionsResponse,
            )
        except LLMError as exc:
            logger.warning(
                "LLM mission generation failed; using deterministic fallback: %s",
                exc,
            )
            return self._fallback_missions(snapshot)
        except Exception as exc:
            logger.warning(
                "Unexpected mission generation failure; using deterministic fallback: %s",
                exc,
            )
            return self._fallback_missions(snapshot)

        if not isinstance(result, MissionsResponse):
            raise LLMError("LLM response did not validate as MissionsResponse")

        validated: list[dict] = []
        for spec in result.missions:
            if not spec.affected_files:
                logger.warning("Skipping mission '%s': no affected_files", spec.title)
                continue
            mission = spec.model_dump()
            if mission["mission_type"] == "test_coverage":
                mission["affected_files"] = self._test_targets(mission["affected_files"])
            validated.append(mission)

        if not validated:
            logger.info("LLM returned no missions; generating deterministic missions from objective metrics")
            validated = self._fallback_missions(snapshot)

        return validated[:10]

    @staticmethod
    def _fallback_missions(snapshot: dict) -> list[dict]:
        """Generate actionable missions when the LLM returns an empty list."""
        python_files = [
            str(path).replace("\\", "/")
            for path in snapshot.get("python_files", [])
            if str(path).lower().endswith(".py")
            and not Path(str(path)).name.startswith("test_")
            and not str(path).replace("\\", "/").startswith("tests/")
        ]
        missions: list[dict] = []

        if int(snapshot.get("test_function_count", 0) or 0) == 0:
            source_files = python_files[:3] or ["README.md"]
            missions.append({
                "title": "Create executable test coverage",
                "problem": "The repository has no executable test functions, so regression behavior is not protected.",
                "mission_type": "test_coverage",
                "affected_files": MissionBuilderAgent._test_targets(source_files),
                "priority": "critical",
                "estimated_effort": "hours",
                "expected_impact": "Adds executable regression tests without modifying production modules.",
                "verification_requirements": ["pytest passes", "ruff clean"],
            })

        doc_pct = float(snapshot.get("documented_functions_pct", 0.0) or 0.0)
        if doc_pct < 90.0 and python_files:
            missions.append({
                "title": "Improve Python documentation",
                "problem": f"Only {doc_pct:.1f}% of Python functions are documented.",
                "mission_type": "documentation",
                "affected_files": python_files[:3],
                "priority": "medium",
                "estimated_effort": "hours",
                "expected_impact": "Improves maintainability and code comprehension.",
                "verification_requirements": ["pytest passes", "ruff clean"],
            })

        lint_count = int(snapshot.get("lint_error_count", 0) or 0)
        if lint_count > 0 and python_files:
            missions.append({
                "title": "Resolve lint findings",
                "problem": f"Ruff reports {lint_count} lint finding(s).",
                "mission_type": "refactor",
                "affected_files": python_files[:3],
                "priority": "high",
                "estimated_effort": "hours",
                "expected_impact": "Improves code quality and catches common defects early.",
                "verification_requirements": ["pytest passes", "ruff clean"],
            })

        todo_count = int(snapshot.get("todo_count", 0) or 0)
        if todo_count > 0 and python_files:
            missions.append({
                "title": "Resolve TODO and FIXME markers",
                "problem": f"The repository contains {todo_count} TODO/FIXME marker(s).",
                "mission_type": "bug_fix",
                "affected_files": python_files[:3],
                "priority": "low",
                "estimated_effort": "hours",
                "expected_impact": "Reduces unresolved implementation debt.",
                "verification_requirements": ["pytest passes", "TODO/FIXME scan passes"],
            })

        return missions

    @staticmethod
    def _test_targets(files: list[str]) -> list[str]:
        """Map source modules to test files; test missions may create these files."""
        targets: list[str] = []
        for value in files:
            path = Path(value)
            normalized = str(path).replace("\\", "/")
            if path.suffix.lower() != ".py":
                continue
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                target = normalized
            else:
                target = f"tests/test_{path.stem}.py"
            if target not in targets:
                targets.append(target)
        return targets or files

    def _build_system_prompt(self) -> str:
        return (
            "You are a senior software engineer performing a code quality review. "
            "Given metrics from a Python repository, generate a prioritized list of actionable engineering missions.\n\n"
            "Each mission must address a real, specific problem visible in the metrics.\n"
            "For test_coverage missions, affected_files are SOURCE modules that need tests; "
            "DevForge will convert them into tests/test_<module>.py targets.\n\n"
            "Respond ONLY with valid JSON matching this exact schema:\n"
            '{"missions": [{"title":"Short mission title","problem":"Specific problem",'
            '"mission_type":"test_coverage|bug_fix|documentation|refactor|dependency_update",'
            '"affected_files":["path/to/file.py"],"priority":"critical|high|medium|low",'
            '"estimated_effort":"minutes|hours|half_day","expected_impact":"Short description",'
            '"verification_requirements":["tests pass","ruff clean"]}]}\n\n'
            "Generate 3–8 missions. If test coverage is below 30%, include at least one test_coverage mission. "
            "Do not include estimated_manual_minutes. Do not generate dependency graphs."
        )

    def _build_user_prompt(self, snapshot: dict) -> str:
        top_issues: list[str] = []
        try:
            top_issues = json.loads(snapshot.get("top_issues", "[]"))
        except (json.JSONDecodeError, TypeError):
            pass

        languages: dict = {}
        try:
            languages = json.loads(snapshot.get("languages", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass

        test_pct = round(
            snapshot.get("test_file_count", 0) / max(snapshot.get("file_count", 1), 1) * 100,
            1,
        )

        return (
            f"Repository metrics:\n"
            f"  Total files: {snapshot.get('file_count', 0)}\n"
            f"  Test files: {snapshot.get('test_file_count', 0)} ({test_pct}% of files)\n"
            f"  Test functions: {snapshot.get('test_function_count', 0)}\n"
            f"  TODO/FIXME count: {snapshot.get('todo_count', 0)}\n"
            f"  Lint errors: {snapshot.get('lint_error_count', 0)}\n"
            f"  Documented functions: {snapshot.get('documented_functions_pct', 0.0)}%\n"
            f"  Languages: {languages}\n\n"
            f"Analysis summary: {snapshot.get('analysis_summary', '')}\n\n"
            f"Identified issues:\n"
            + ("\n".join(f"  - {issue}" for issue in top_issues) or "  (none identified)")
        )
