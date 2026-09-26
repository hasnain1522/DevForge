"""
MissionBuilderAgent — converts a RepositorySnapshot into prioritized engineering Missions.

The LLM receives the actual snapshot metrics and issues.
All generated missions are validated against MissionSpec via Pydantic.

IMPORTANT:
- estimated_effort and expected_impact are informational display text only.
- estimated_manual_minutes does NOT exist.
- No dependency graphs are generated.
- No execution orchestration happens here.
- If the LLM fails, a clear LLMError is raised — no fabricated missions.
"""
import json
import logging

from pydantic import BaseModel, field_validator

from devforge.agents.base import BaseAgent
from devforge.utils.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)

VALID_MISSION_TYPES = frozenset({
    "bug_fix", "test_coverage", "documentation", "refactor", "dependency_update"
})
VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
VALID_EFFORTS = frozenset({"minutes", "hours", "half_day"})


# ---------------------------------------------------------------------------
# Pydantic schema for LLM response validation
# ---------------------------------------------------------------------------

class MissionSpec(BaseModel):
    """
    Schema for a single mission returned by the LLM.
    Used to validate the LLM response before persisting.
    """
    title: str
    problem: str
    mission_type: str
    affected_files: list[str]
    priority: str
    estimated_effort: str  # informational only
    expected_impact: str   # informational only
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
        if v not in VALID_PRIORITIES:
            return "medium"  # safe fallback for borderline cases
        return v

    @field_validator("estimated_effort")
    @classmethod
    def validate_effort(cls, v: str) -> str:
        if v not in VALID_EFFORTS:
            return "hours"  # safe fallback
        return v

    @field_validator("affected_files")
    @classmethod
    def validate_affected_files(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("affected_files must not be empty")
        return v


class MissionsResponse(BaseModel):
    """Top-level wrapper expected from the LLM."""
    missions: list[MissionSpec]


# ---------------------------------------------------------------------------
# Priority sort order
# ---------------------------------------------------------------------------

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class MissionBuilderAgent(BaseAgent):
    """
    Generates prioritized engineering Missions from a RepositorySnapshot.

    Phase 2 implementation.
    """

    name = "mission_builder"

    def __init__(self, llm: LLMClient) -> None:
        super().__init__()
        self.llm = llm

    async def run(self, context: dict) -> dict:
        """
        Generate missions from the snapshot in context["snapshot"].

        context must contain:
            snapshot: dict  — the RepositorySnapshot field dict

        Returns:
            {"missions": list[dict]}  — each dict matches MissionSpec fields.

        Raises:
            LLMError if the LLM fails after retries.
            ValueError if the snapshot is missing required fields.
        """
        snapshot = context.get("snapshot")
        if not snapshot:
            raise ValueError("context must contain 'snapshot'")

        missions_raw = await self._generate(snapshot)

        # Sort by priority
        missions_raw.sort(key=lambda m: _PRIORITY_ORDER.get(m["priority"], 99))

        return {"missions": missions_raw}

    async def _generate(self, snapshot: dict) -> list[dict]:
        """Call the LLM and validate the response. Returns a list of mission dicts."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(snapshot)

        try:
            result = await self.llm.call_json(
                system_prompt, user_prompt, response_model=MissionsResponse
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Unexpected error during mission generation: {exc}") from exc

        missions_response = result  # type: MissionsResponse
        if not isinstance(missions_response, MissionsResponse):
            # call_json without response_model returns a dict; shouldn't happen here
            raise LLMError("LLM response did not validate as MissionsResponse")

        validated: list[dict] = []
        for spec in missions_response.missions:
            # Additional guard: skip if affected_files is somehow empty
            if not spec.affected_files:
                logger.warning("Skipping mission '%s': no affected_files", spec.title)
                continue
            validated.append(spec.model_dump())

        # Cap at 10 missions
        validated = validated[:10]

        self.logger.info("Generated %d missions", len(validated))
        return validated

    # ── Prompt construction ─────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return (
            "You are a senior software engineer performing a code quality review. "
            "Given metrics from a Python repository, generate a prioritized list of "
            "actionable engineering missions.\n\n"
            "Each mission must address a real, specific problem visible in the metrics.\n"
            "Each mission must reference at least one plausible file path from the repository.\n\n"
            "Respond ONLY with valid JSON matching this exact schema:\n"
            '{"missions": [\n'
            '  {\n'
            '    "title": "Short mission title",\n'
            '    "problem": "Specific description of what is wrong",\n'
            '    "mission_type": "test_coverage|bug_fix|documentation|refactor|dependency_update",\n'
            '    "affected_files": ["path/to/file.py"],\n'
            '    "priority": "critical|high|medium|low",\n'
            '    "estimated_effort": "minutes|hours|half_day",\n'
            '    "expected_impact": "Short description of improvement",\n'
            '    "verification_requirements": ["tests pass", "ruff clean"]\n'
            '  }\n'
            "]}\n\n"
            "Generate 3–8 missions. "
            "If test coverage is below 30%, include at least one test_coverage mission. "
            "Do not include estimated_manual_minutes. "
            "Do not generate dependency graphs."
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

        test_pct = (
            round(snapshot.get("test_file_count", 0) / max(snapshot.get("file_count", 1), 1) * 100, 1)
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
