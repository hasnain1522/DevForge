"""
RepositoryAnalyzerAgent — analyzes a Python repository and produces a RepositorySnapshot.

All metrics are computed from objective sources:
  file_count            — filesystem traversal
  test_file_count       — filename pattern matching
  test_function_count   — Python AST
  todo_count            — text grep for TODO / FIXME
  lint_error_count      — ruff subprocess (via ruff_counter)
  documented_functions  — Python AST docstring inspection
  languages             — extension counts via file_tree.detect_languages

The LLM is called ONCE at the end to produce top_issues and analysis_summary from
the already-computed metrics + file tree.  It is not used for any numeric measurement.
"""
import ast
import json
import logging
import re
from pathlib import Path

from devforge.agents.base import BaseAgent
from devforge.utils.file_tree import PYTHON_EXTENSIONS, detect_languages, walk_repository
from devforge.utils.llm import LLMClient
from devforge.utils.ruff_counter import count_ruff_errors

logger = logging.getLogger(__name__)

# Pattern: test files
_TEST_FILE_RE = re.compile(r"(^|[\\/])(test_[^/\\]+|[^/\\]+_test)\.py$")


# ---------------------------------------------------------------------------
# Pure static-analysis helpers (no I/O side effects, easy to unit-test)
# ---------------------------------------------------------------------------

def _is_test_file(rel_path: str) -> bool:
    """Return True if the file looks like a pytest test file."""
    return bool(_TEST_FILE_RE.search(rel_path.replace("\\", "/")))


def _count_test_functions_in_source(source: str) -> int:
    """Return the number of functions named test_* in a Python source string."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            count += 1
    return count


def _count_todo_in_source(source: str) -> int:
    """Return the number of TODO/FIXME occurrences in a source string."""
    return len(re.findall(r"\b(TODO|FIXME)\b", source, re.IGNORECASE))


def _documented_functions_pct(source: str) -> tuple[int, int]:
    """
    Return (documented_count, total_count) for all functions in source.

    A function is considered documented if its first statement is a string literal.
    Returns (0, 0) if the file cannot be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, 0

    total = 0
    documented = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            # Check for docstring: first body statement is Expr(Constant(str))
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                documented += 1
    return documented, total


# ---------------------------------------------------------------------------
# Analyzer agent
# ---------------------------------------------------------------------------

class RepositoryAnalyzerAgent(BaseAgent):
    """
    Analyzes a Python repository and produces a RepositorySnapshot dict.

    Phase 2 implementation. Language scope: Python (MVP).
    """

    name = "analyzer"

    def __init__(self, llm: LLMClient) -> None:
        super().__init__()
        self.llm = llm

    async def run(self, context: dict) -> dict:
        """
        Analyze the repository at context["repo_path"].

        Returns a dict matching the RepositorySnapshot field names.
        Raises ValueError for invalid paths.
        Raises LLMError if the LLM call fails after retries.
        """
        repo_path = context["repo_path"]
        resolved = Path(repo_path).resolve()

        if not resolved.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not resolved.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo_path}")

        self.logger.info("Analyzing repository: %s", resolved)

        # ── Step 1: walk the file tree ──────────────────────────────────────
        all_files = walk_repository(str(resolved))
        file_count = len(all_files)
        self.logger.info("Files found: %d", file_count)

        # ── Step 2: language detection ──────────────────────────────────────
        languages = detect_languages(all_files)

        # ── Step 3: Python-file metrics ─────────────────────────────────────
        python_files = [f for f in all_files if Path(f).suffix.lower() in PYTHON_EXTENSIONS]

        test_file_count = sum(1 for f in python_files if _is_test_file(f))

        test_function_count = 0
        todo_count = 0
        total_funcs = 0
        documented_funcs = 0

        for rel_path in python_files:
            full_path = resolved / rel_path
            try:
                source = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self.logger.warning("Could not read %s: %s", rel_path, exc)
                continue

            test_function_count += _count_test_functions_in_source(source)
            todo_count += _count_todo_in_source(source)

            doc, tot = _documented_functions_pct(source)
            documented_funcs += doc
            total_funcs += tot

        documented_functions_pct = (
            round(documented_funcs / total_funcs * 100, 1) if total_funcs > 0 else 0.0
        )

        # ── Step 4: lint baseline ────────────────────────────────────────────
        ruff_result = count_ruff_errors(str(resolved))
        lint_error_count = ruff_result.error_count
        if not ruff_result.available:
            self.logger.warning("ruff not available; lint_error_count set to 0")

        # ── Step 5: manifest reading (for LLM context) ───────────────────────
        manifest_content = _read_manifests(resolved)

        # ── Step 6: LLM call for top_issues + analysis_summary ───────────────
        top_issues, analysis_summary = await self._call_llm(
            repo_path=str(resolved),
            file_count=file_count,
            python_file_count=len(python_files),
            test_file_count=test_file_count,
            test_function_count=test_function_count,
            todo_count=todo_count,
            lint_error_count=lint_error_count,
            documented_functions_pct=documented_functions_pct,
            languages=languages,
            manifest_content=manifest_content,
            file_sample=all_files[:50],  # first 50 paths for context
        )

        result = {
            "file_count": file_count,
            "test_file_count": test_file_count,
            "test_function_count": test_function_count,
            "todo_count": todo_count,
            "lint_error_count": lint_error_count,
            "documented_functions_pct": documented_functions_pct,
            "languages": json.dumps(languages),
            "top_issues": json.dumps(top_issues),
            "analysis_summary": analysis_summary,
        }
        self.logger.info("Analysis complete: %s", {k: v for k, v in result.items() if k != "analysis_summary"})
        return result

    async def _call_llm(self, **kwargs) -> tuple[list[str], str]:
        """
        Call the LLM with the computed metrics to get top_issues and analysis_summary.

        Returns (top_issues: list[str], analysis_summary: str).
        On LLM failure: returns empty issues and a fallback summary built from metrics.
        """
        file_sample_str = "\n".join(kwargs["file_sample"])
        manifest_str = kwargs["manifest_content"] or "(no manifest files found)"

        system_prompt = (
            "You are a software engineering analyst. "
            "Given metrics and file structure from a Python repository, "
            "identify the top engineering issues and write a concise summary. "
            "Respond ONLY with valid JSON in this exact schema:\n"
            '{"top_issues": ["issue 1", "issue 2", ...], "analysis_summary": "..."}\n'
            "top_issues: list of 3–8 concise issue strings (e.g. 'Low test coverage in auth module').\n"
            "analysis_summary: 2–4 sentence plain-English description of the repository state."
        )
        user_prompt = (
            f"Repository path: {kwargs['repo_path']}\n\n"
            f"Metrics:\n"
            f"  total files: {kwargs['file_count']}\n"
            f"  python files: {kwargs['python_file_count']}\n"
            f"  test files: {kwargs['test_file_count']}\n"
            f"  test functions: {kwargs['test_function_count']}\n"
            f"  TODO/FIXME count: {kwargs['todo_count']}\n"
            f"  lint errors: {kwargs['lint_error_count']}\n"
            f"  documented functions %: {kwargs['documented_functions_pct']}\n"
            f"  languages: {kwargs['languages']}\n\n"
            f"Manifest files:\n{manifest_str}\n\n"
            f"File list (first 50):\n{file_sample_str}"
        )

        try:
            data = await self.llm.call_json(system_prompt, user_prompt)
            top_issues = data.get("top_issues", [])  # type: ignore[union-attr]
            if not isinstance(top_issues, list):
                top_issues = []
            # Limit to 10 issues max
            top_issues = [str(i) for i in top_issues[:10]]
            summary = str(data.get("analysis_summary", ""))  # type: ignore[union-attr]
            return top_issues, summary
        except Exception as exc:  # noqa: BLE001 — any API/network/auth error falls back
            self.logger.warning("LLM analysis failed: %s — using fallback summary", exc)
            fallback_summary = (
                f"Repository contains {kwargs['file_count']} files "
                f"({kwargs['python_file_count']} Python). "
                f"Test functions: {kwargs['test_function_count']}. "
                f"Lint errors: {kwargs['lint_error_count']}. "
                f"Documented functions: {kwargs['documented_functions_pct']}%."
            )
            return [], fallback_summary


# ---------------------------------------------------------------------------
# Helper: read manifest files for LLM context
# ---------------------------------------------------------------------------

_MANIFEST_NAMES = ["README.md", "pyproject.toml", "requirements.txt", "setup.cfg", "Makefile"]
_MANIFEST_MAX_CHARS = 3000  # total chars to pass to LLM


def _read_manifests(root: Path) -> str:
    """Read key manifest files and return their content (truncated) as a string."""
    parts: list[str] = []
    remaining = _MANIFEST_MAX_CHARS
    for name in _MANIFEST_NAMES:
        candidate = root / name
        if candidate.is_file():
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
                snippet = content[:remaining]
                parts.append(f"--- {name} ---\n{snippet}")
                remaining -= len(snippet)
                if remaining <= 0:
                    break
            except OSError:
                pass
    return "\n\n".join(parts)
