"""Deterministic mission templates and execution coordination."""

from devforge.agents.documenter import DocumenterAgent
from devforge.agents.implementer import ImplementerAgent
from devforge.agents.tester import TesterAgent
from devforge.verification.runner import (
    VerificationFailure,
    VerificationRunner,
)

TEMPLATES = {
    "bug_fix": ("implementer", "tester"),
    "test_coverage": ("implementer", "tester"),
    "documentation": ("documenter", "tester"),
    "refactor": ("implementer", "tester"),
    "dependency_update": ("implementer", "tester"),
}


class AgentOrchestrator:
    def __init__(self, llm, emit):
        self.llm = llm
        self.emit = emit

    async def run(self, mission: dict, repo_path: str) -> dict:
        mission_type = mission["mission_type"]

        if mission_type not in TEMPLATES:
            raise ValueError(f"Unsupported mission type: {mission_type}")

        files = mission["affected_files"]

        if not files:
            raise ValueError("Mission has no affected files")

        completed_before = set(
            mission.get("resume_completed_files", [])
        )

        pending_files = [
            path for path in files
            if path not in completed_before
        ]

        retry_mode = bool(mission.get("retry_mode"))

        async def emit_agent(
            agent: str,
            event_type: str,
            message: str,
            target_file=None,
        ):
            if retry_mode and agent == "documenter" and target_file:
                event_type = {
                    "started": "file_retry_started",
                    "completed": "file_retry_completed",
                    "failed": "file_retry_failed",
                }.get(event_type, event_type)

            await self.emit(
                agent,
                event_type,
                message,
                target_file,
            )

        context = {
            **mission,
            "files": pending_files,
            "repo_path": repo_path,
            "retry_mode": retry_mode,
        }

        await self.emit(
            "orchestrator",
            "started",
            f"Starting {mission_type} mission with {len(files)} file(s)",
        )

        for filename in files:
            if filename in completed_before:
                await self.emit(
                    "orchestrator",
                    "file_skipped",
                    f"Skipped {filename} — previously completed",
                    str(filename),
                )

        changed: list[str] = []

        implementation = {
            "changed_files": [],
            "file_changes": [],
            "failures": [],
        }

        if pending_files:
            if mission_type == "documentation":
                implementation = await DocumenterAgent(
                    self.llm,
                    emit_agent,
                ).run(context)
            else:
                implementation = await ImplementerAgent(
                    self.llm,
                    emit_agent,
                ).run(context)

            changed.extend(
                implementation["changed_files"]
            )

        if implementation.get("failures"):
            failure = implementation["failures"][0]

            await self.emit(
                "orchestrator",
                "failed",
                failure["reason"],
                failure["filename"],
            )

            return {
                "changed_files": changed,
                "file_changes": implementation["file_changes"],
                "verification": None,
                "failure": failure,
                "subtask_count": 2,
                "subtasks_completed": 0,
                "subtasks_failed": 1,
            }

        # Verification runs only after implementation completes.
        try:
            verification = await TesterAgent(
                VerificationRunner(),
                emit_agent,
            ).run(context)

        except VerificationFailure as exc:
            # Preserve the structured verification failure.
            failure = {
                "stage": exc.stage,
                "category": exc.category,
                "reason": exc.reason,
                "command": exc.command,
                "exit_code": exc.exit_code,
            }

            await self.emit(
                "orchestrator",
                "failed",
                f"Check: {exc.command} — {exc.reason}",
            )

            return {
                "changed_files": changed,
                "file_changes": implementation["file_changes"],
                "verification": None,
                "failure": failure,
                "subtask_count": 2,
                "subtasks_completed": 1,
                "subtasks_failed": 1,
            }

        except NotImplementedError as exc:
            # Capture unexpected NotImplementedError without
            # hiding the actual reason.
            detail = str(exc).strip() or (
                "No additional error detail was provided."
            )

            failure = {
                "stage": "verification",
                "category": "tester_error",
                "reason": (
                    f"Tester failed (NotImplementedError): {detail}"
                ),
                "command": "verification",
                "exit_code": None,
            }

            await self.emit(
                "orchestrator",
                "failed",
                failure["reason"],
            )

            return {
                "changed_files": changed,
                "file_changes": implementation["file_changes"],
                "verification": None,
                "failure": failure,
                "subtask_count": 2,
                "subtasks_completed": 1,
                "subtasks_failed": 1,
            }

        return {
            "changed_files": changed,
            "file_changes": implementation["file_changes"],
            "verification": verification,
            "subtask_count": 2,
            "subtasks_completed": (
                2 if verification["passed"] else 1
            ),
            "subtasks_failed": (
                0 if verification["passed"] else 1
            ),
        }