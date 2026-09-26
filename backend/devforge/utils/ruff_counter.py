"""
ruff_counter — run ruff against a repository and count lint violations.

This function is called by:
  - RepositoryAnalyzerAgent  → populates lint_error_count in the BEFORE snapshot
  - VerificationRunner (Phase 3) → populates lint_errors in verification_results

Both are real subprocess invocations; results are always objective tool output.
"""
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RuffResult:
    """Structured result from a ruff check run."""

    error_count: int
    """Total number of lint violations found."""

    available: bool
    """False when ruff could not be executed (not installed / subprocess error)."""

    raw_output: str
    """Full stdout from ruff for debugging."""


def count_ruff_errors(repo_path: str) -> RuffResult:
    """
    Run `ruff check --output-format=json` on repo_path and return a RuffResult.

    - Returns error_count=0, available=False if ruff cannot be executed.
    - Returns error_count=0, available=True if ruff runs but finds no issues.
    - Never raises; all errors are caught and logged.
    """
    resolved = Path(repo_path).resolve()
    if not resolved.is_dir():
        logger.warning("ruff_counter: path is not a directory: %s", repo_path)
        return RuffResult(error_count=0, available=False, raw_output="")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--output-format=json", str(resolved)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ruff_counter: ruff not found; returning 0")
        return RuffResult(error_count=0, available=False, raw_output="")
    except subprocess.TimeoutExpired:
        logger.warning("ruff_counter: timed out on %s", repo_path)
        return RuffResult(error_count=0, available=False, raw_output="timeout")
    except OSError as exc:
        logger.warning("ruff_counter: OS error running ruff: %s", exc)
        return RuffResult(error_count=0, available=False, raw_output=str(exc))

    raw = result.stdout.strip()

    # ruff exits 0 (no issues) or 1 (issues found); both are valid runs.
    # Any other exit code (e.g. 2 = internal error) means the run failed.
    if result.returncode not in (0, 1):
        logger.warning(
            "ruff_counter: unexpected exit code %d; stderr: %s",
            result.returncode,
            result.stderr[:200],
        )
        return RuffResult(error_count=0, available=False, raw_output=raw or result.stderr)

    if not raw:
        # No JSON output → no violations
        return RuffResult(error_count=0, available=True, raw_output="")

    try:
        violations = json.loads(raw)
        count = len(violations) if isinstance(violations, list) else 0
        return RuffResult(error_count=count, available=True, raw_output=raw)
    except json.JSONDecodeError as exc:
        logger.warning("ruff_counter: failed to parse JSON output: %s", exc)
        return RuffResult(error_count=0, available=False, raw_output=raw)
