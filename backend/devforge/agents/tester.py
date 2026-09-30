"""Execute configured repository verification and report actual outcomes."""
from devforge.agents.base import BaseAgent
from devforge.verification.runner import VerificationFailure, VerificationRunner


class TesterAgent(BaseAgent):
    name = "tester"

    def __init__(self, runner: VerificationRunner, emit):
        super().__init__()
        self.runner = runner
        self.emit = emit

    async def run(self, context: dict) -> dict:
        requirements = list(context.get("verification_requirements") or [
            "pytest passes",
            "ruff clean",
        ])
        # A test-coverage mission should verify the tests it added, not fail
        # because unrelated pre-existing TODO/FIXME debt exists elsewhere in
        # the repository. TODO cleanup is a separate bug-fix mission.
        if context.get("mission_type") == "test_coverage":
            requirements = [
                item for item in requirements
                if "todo" not in item.lower() and "fixme" not in item.lower()
            ]
        if not requirements:
            requirements = ["pytest passes"]
        await self.emit(
            "tester",
            "started",
            "Running configured verification: " + ", ".join(requirements),
        )
        try:
            result = await self.runner.run(context["repo_path"], requirements)
        except VerificationFailure as exc:
            await self.emit(
                "tester",
                "failed",
                f"{exc.category}: {exc.reason} Command: {exc.command}.",
            )
            raise
        state = "completed" if result["passed"] else "failed"
        message = (
            f"{result['pass_count']} passed, {result['fail_count']} failed; "
            f"{result['lint_errors']} ruff findings"
        )
        if result.get("failure"):
            failure = result["failure"]
            message += f"; {failure['reason']}"
        await self.emit("tester", state, message)
        return result
