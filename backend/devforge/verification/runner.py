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
            *command, cwd=str(cwd), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, env=env,
        )
        output, _ = await process.communicate()
        return process.returncode or 0, _redact(output.decode(errors="replace"))
    except FileNotFoundError as exc:
        raise VerificationFailure(
            category="command_unavailable",
            reason=f"Could not start {check_name}: the Python verification command is unavailable.",
            command=check_name, exit_code=127,
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
    return {"stage": "verification", "category": category, "reason": reason,
            "command": check, "exit_code": code}


class VerificationRunner:
    async def run(self, repo_path: str) -> dict:
        root = Path(repo_path).resolve()
        if not root.is_dir():
            raise VerificationFailure(
                category="repository_workspace_unavailable",
                reason="The isolated repository workspace is unavailable for verification.",
                command="pytest",
            )
        pytest_code, pytest_output = await _run(
            [sys.executable, "-m", "pytest", "-q"], root, "pytest",
        )
        ruff_code, ruff_output = await _run(
            [sys.executable, "-m", "ruff", "check", "--output-format=json", "."], root, "ruff",
        )
        todo_code, todo_output = await _run(
            [sys.executable, "-c", ("from pathlib import Path; import re,sys; "
             "files=[p for p in Path('.').rglob('*.py') if not any(x in p.parts for x in "
             "('.git','.venv','venv','__pycache__','.pytest_cache'))]; "
             "hits=[f'{p}:{i}:{line.strip()}' for p in files for i,line in "
             "enumerate(p.read_text(errors='replace').splitlines(),1) if re.search(r'\\b(TODO|FIXME)\\b',line,re.I)]; "
             "print('\\n'.join(hits)); sys.exit(bool(hits))")], root, "TODO/FIXME scan",
        )
        passed = sum(int(x) for x in re.findall(r"(\d+) passed", pytest_output))
        failed = sum(int(x) for x in re.findall(r"(\d+) failed", pytest_output))
        errors = sum(int(x) for x in re.findall(r"(\d+) error", pytest_output))
        try:
            lint_errors = len(json.loads(ruff_output))
        except json.JSONDecodeError:
            lint_errors = 0 if ruff_code == 0 else 1
        coverage = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", pytest_output)
        checks = [
            {"check": "pytest", "command": "python -m pytest -q", "exit_code": pytest_code,
             "passed": pytest_code == 0},
            {"check": "ruff", "command": "python -m ruff check --output-format=json .",
             "exit_code": ruff_code, "passed": ruff_code == 0, "finding_count": lint_errors},
            {"check": "TODO/FIXME scan", "command": "python -c <TODO/FIXME scan>",
             "exit_code": todo_code, "passed": todo_code == 0},
        ]
        failures = (
            _check_failure("pytest", pytest_code, pytest_output)
            if pytest_code else None,
            _check_failure("ruff", ruff_code, ruff_output, lint_errors)
            if ruff_code else None,
            _check_failure("TODO/FIXME scan", todo_code, todo_output)
            if todo_code else None,
        )
        failure = next((item for item in failures if item), None)
        output = (f"$ python -m pytest -q\n{pytest_output}\n"
                  f"$ python -m ruff check .\n{ruff_output}\n"
                  f"$ TODO/FIXME scan\n{todo_output}")
        return asdict(VerificationResult(
            passed=pytest_code == 0 and ruff_code == 0 and todo_code == 0,
            test_count=passed + failed + errors, pass_count=passed,
            fail_count=failed + errors, lint_errors=lint_errors,
            coverage_pct=float(coverage.group(1)) if coverage else None,
            raw_output=output, checks=checks, failure=failure,
        ))
