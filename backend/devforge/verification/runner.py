"""Run real Python verification commands and return their observed results."""
import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from devforge.config import settings


@dataclass
class VerificationResult:
    passed: bool
    test_count: int
    pass_count: int
    fail_count: int
    lint_errors: int
    coverage_pct: float | None
    raw_output: str
    checks: list[dict]
    failure: dict | None


class VerificationFailure(RuntimeError):
    """Safe, structured failure raised when a verification command cannot run."""

    def __init__(self, *, category: str, reason: str, command: str, exit_code: int | None = None):
        self.stage = "verification"
        self.category = category
        self.reason = reason
        self.command = command
        self.exit_code = exit_code
        super().__init__(reason)


_SECRET_ENV = ("LLM_API_KEY", "OPENROUTER_API_KEY", "AUTH_SECRET")


def _redact(text: str) -> str:
    for secret in (settings.llm_api_key, settings.openrouter_api_key, settings.auth_secret):
        if secret and secret != "not-configured":
            text = text.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)(sk-[A-Za-z0-9_-]{12,}|Bearer\s+\S+)", "[REDACTED]", text)


async def _run(command: list[str], cwd: Path, check_name: str) -> tuple[int, str]:
    env = os.environ.copy()
    for name in _SECRET_ENV:
        env.pop(name, None)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        output, _ = await process.communicate()
        return process.returncode or 0, _redact(output.decode(errors="replace"))
    except FileNotFoundError as exc:
        raise VerificationFailure(
            category="command_unavailable",
            reason=f"Could not start {check_name}: the Python verification command is unavailable.",
            command=check_name,
            exit_code=127,
        ) from exc
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise VerificationFailure(
            category="command_start_failed",
            reason=f"Could not start {check_name} ({type(exc).__name__}).",
            command=check_name,
        ) from exc


def _check_failure(check: str, code: int, output: str, lint_errors: int = 0) -> dict:
    if check == "pytest":
        if code == 5:
            reason = "pytest collected no tests (exit code 5)."
            category = "no_tests_collected"
        else:
            summary = re.search(r"\d+ failed(?:, \d+ passed)?|\d+ error(?:s)?", output)
            detail = f"; {summary.group(0)}" if summary else ""
            reason = f"pytest failed{detail} (exit code {code})."
            category = "test_failure"
    elif check == "ruff":
        reason = f"Ruff reported {lint_errors} finding(s) (exit code {code})."
        category = "lint_failure"
    else:
        reason = "TODO/FIXME scan found matching markers (exit code 1)."
        category = "todo_markers_found"
    return {
        "stage": "verification",
        "category": category,
        "reason": reason,
        "command": check,
        "exit_code": code,
    }


class VerificationRunner:
    async def run(self, repo_path: str, requirements: list[str] | None = None) -> dict:
        root = Path(repo_path).resolve()
        if not root.is_dir():
            raise VerificationFailure(
                category="repository_workspace_unavailable",
                reason="The isolated repository workspace is unavailable for verification.",
                command="pytest",
            )

        normalized = [
            item.lower()
            for item in (requirements or ["pytest passes", "ruff clean", "TODO/FIXME scan passes"])
        ]
        run_pytest = any("pytest" in item or "test" in item for item in normalized)
        run_ruff = any("ruff" in item for item in normalized)
        run_todo = any("todo" in item or "fixme" in item for item in normalized)

        pytest_code, pytest_output = 0, "Skipped: not required by this mission."
        if run_pytest:
            pytest_code, pytest_output = await _run(
                [sys.executable, "-m", "pytest", "-q"], root, "pytest"
            )

        ruff_code, ruff_output = 0, "Skipped: not required by this mission."
        if run_ruff:
            ruff_code, ruff_output = await _run(
                [sys.executable, "-m", "ruff", "check", "--output-format=json", "."],
                root,
                "ruff",
            )

        todo_code, todo_output = 0, "Skipped: not required by this mission."
        if run_todo:
            # Keep the marker scan in-process. Embedding Python source inside
            # another Python string is fragile: \b can become a backspace and
            # escaped newlines can corrupt the generated command.
            ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
            hits: list[str] = []
            for file_path in root.rglob("*.py"):
                if any(part in ignored for part in file_path.parts):
                    continue
                try:
                    lines = file_path.read_text(errors="replace").splitlines()
                except OSError:
                    continue
                for line_number, line in enumerate(lines, 1):
                    if re.search(r"\b(TODO|FIXME)\b", line, re.IGNORECASE):
                        relative = file_path.relative_to(root)
                        hits.append(f"{relative}:{line_number}:{line.strip()}")
            todo_code = 1 if hits else 0
            todo_output = "\n".join(hits) if hits else "No TODO/FIXME markers found."

        passed = sum(int(x) for x in re.findall(r"(\d+) passed", pytest_output)) if run_pytest else 0
        failed = sum(int(x) for x in re.findall(r"(\d+) failed", pytest_output)) if run_pytest else 0
        errors = sum(int(x) for x in re.findall(r"(\d+) error", pytest_output)) if run_pytest else 0

        try:
            lint_errors = len(json.loads(ruff_output)) if run_ruff else 0
        except json.JSONDecodeError:
            lint_errors = 0 if ruff_code == 0 else 1

        coverage = (
            re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", pytest_output)
            if run_pytest
            else None
        )

        checks = []
        if run_pytest:
            checks.append({
                "check": "pytest",
                "command": "python -m pytest -q",
                "exit_code": pytest_code,
                "passed": pytest_code == 0,
            })
        if run_ruff:
            checks.append({
                "check": "ruff",
                "command": "python -m ruff check --output-format=json .",
                "exit_code": ruff_code,
                "passed": ruff_code == 0,
                "finding_count": lint_errors,
            })
        if run_todo:
            checks.append({
                "check": "TODO/FIXME scan",
                "command": "python -c <TODO/FIXME scan>",
                "exit_code": todo_code,
                "passed": todo_code == 0,
            })

        failures = (
            _check_failure("pytest", pytest_code, pytest_output)
            if run_pytest and pytest_code
            else None,
            _check_failure("ruff", ruff_code, ruff_output, lint_errors)
            if run_ruff and ruff_code
            else None,
            _check_failure("TODO/FIXME scan", todo_code, todo_output)
            if run_todo and todo_code
            else None,
        )
        failure = next((item for item in failures if item), None)

        output_parts = []
        if run_pytest:
            output_parts.append(f"$ python -m pytest -q\n{pytest_output}")
        if run_ruff:
            output_parts.append(f"$ python -m ruff check .\n{ruff_output}")
        if run_todo:
            output_parts.append(f"$ TODO/FIXME scan\n{todo_output}")

        return asdict(
            VerificationResult(
                passed=(
                    (not run_pytest or pytest_code == 0)
                    and (not run_ruff or ruff_code == 0)
                    and (not run_todo or todo_code == 0)
                ),
                test_count=passed + failed + errors,
                pass_count=passed,
                fail_count=failed + errors,
                lint_errors=lint_errors,
                coverage_pct=float(coverage.group(1)) if coverage else None,
                raw_output="\n".join(output_parts),
                checks=checks,
                failure=failure,
            )
        )
