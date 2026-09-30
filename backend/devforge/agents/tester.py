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
        requirements = context.get("verification_requirements") or [
            "pytest passes",
            "ruff clean",
            "TODO/FIXME scan passes",
        ]
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
