"""Phase 2 tests for RepositoryAnalyzerAgent, ruff_counter, and static analysis helpers."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from devforge.agents.analyzer import (
    RepositoryAnalyzerAgent,
    _count_test_functions_in_source,
    _count_todo_in_source,
    _documented_functions_pct,
    _is_test_file,
)
from devforge.utils.ruff_counter import RuffResult, count_ruff_errors
from tests.fixtures.fixture_repo import create_fixture_repo

# ---------------------------------------------------------------------------
# Static helper unit tests (no I/O, no LLM)
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_test_prefix(self):
        assert _is_test_file("tests/test_auth.py") is True

    def test_test_suffix(self):
        assert _is_test_file("auth/auth_test.py") is True

    def test_not_test(self):
        assert _is_test_file("auth/validators.py") is False

    def test_nested_test(self):
        assert _is_test_file("src/tests/test_models.py") is True


class TestCountTestFunctions:
    def test_basic(self):
        source = """
def test_foo():
    pass

def test_bar():
    pass

def helper():
    pass
"""
        assert _count_test_functions_in_source(source) == 2

    def test_no_tests(self):
        assert _count_test_functions_in_source("def foo(): pass") == 0

    def test_invalid_syntax(self):
        assert _count_test_functions_in_source("def broken(") == 0

    def test_async_test(self):
        source = "async def test_async(): pass"
        assert _count_test_functions_in_source(source) == 1


class TestCountTodo:
    def test_counts_todo(self):
        source = "# TODO: fix this\nx = 1  # FIXME: also this"
        assert _count_todo_in_source(source) == 2

    def test_case_insensitive(self):
        assert _count_todo_in_source("# todo: lower case") == 1

    def test_no_todos(self):
        assert _count_todo_in_source("x = 1") == 0


class TestDocumentedFunctionsPct:
    def test_all_documented(self):
        source = '''
def foo():
    """Docstring."""
    pass

def bar():
    """Another."""
    pass
'''
        doc, total = _documented_functions_pct(source)
        assert total == 2
        assert doc == 2

    def test_none_documented(self):
        source = "def foo(): pass\ndef bar(): pass"
        doc, total = _documented_functions_pct(source)
        assert total == 2
        assert doc == 0

    def test_empty_file(self):
        doc, total = _documented_functions_pct("")
        assert total == 0
        assert doc == 0

    def test_invalid_syntax(self):
        doc, total = _documented_functions_pct("def broken(")
        assert total == 0
        assert doc == 0


# ---------------------------------------------------------------------------
# ruff_counter tests
# ---------------------------------------------------------------------------

class TestRuffCounter:
    def test_invalid_path(self):
        result = count_ruff_errors("/nonexistent/path/that/does/not/exist")
        assert result.available is False
        assert result.error_count == 0

    def test_clean_repo(self, tmp_path):
        """A repo with no Python files should return 0 errors."""
        result = count_ruff_errors(str(tmp_path))
        # ruff should be available since it's in our dev deps
        assert isinstance(result.error_count, int)
        assert result.error_count == 0

    def test_fixture_repo_has_lint_errors(self, tmp_path):
        """Fixture repo has an unused import — ruff should catch it."""
        repo = create_fixture_repo(tmp_path)
        result = count_ruff_errors(str(repo))
        if result.available:
            assert result.error_count >= 1, "Expected at least 1 lint error (unused import)"

    def test_returns_ruff_result_type(self, tmp_path):
        result = count_ruff_errors(str(tmp_path))
        assert isinstance(result, RuffResult)
        assert isinstance(result.error_count, int)
        assert isinstance(result.available, bool)


# ---------------------------------------------------------------------------
# RepositoryAnalyzerAgent integration tests (mock LLM)
# ---------------------------------------------------------------------------

def _make_mock_llm(top_issues=None, summary="Test summary"):
    """Create a mock LLMClient that returns a preset response."""
    mock = MagicMock()
    mock.call_json = AsyncMock(return_value={
        "top_issues": top_issues or ["Low test coverage"],
        "analysis_summary": summary,
    })
    return mock


class TestRepositoryAnalyzerAgent:
    @pytest.mark.asyncio
    async def test_basic_metrics(self, tmp_path):
        """Analyzer should compute correct file/test counts on the fixture repo."""
        repo = create_fixture_repo(tmp_path)
        agent = RepositoryAnalyzerAgent(llm=_make_mock_llm())

        result = await agent.run({"repo_path": str(repo)})

        # 6 .py files total (including __init__.py files and pyproject.toml skipped)
        # auth/__init__.py, auth/validators.py, utils/__init__.py, utils/helpers.py,
        # tests/__init__.py, tests/test_auth.py, tests/test_utils.py = 7 py files
        assert result["file_count"] >= 6
        assert result["test_file_count"] == 2  # test_auth.py, test_utils.py
        assert result["test_function_count"] == 3  # test_validate_email, test_hash_password, test_format_name

    @pytest.mark.asyncio
    async def test_todo_count(self, tmp_path):
        """Analyzer should find the 3 TODO/FIXME comments in the fixture repo."""
        repo = create_fixture_repo(tmp_path)
        agent = RepositoryAnalyzerAgent(llm=_make_mock_llm())

        result = await agent.run({"repo_path": str(repo)})
        assert result["todo_count"] == 3  # 2 TODO + 1 FIXME

    @pytest.mark.asyncio
    async def test_documented_functions_pct(self, tmp_path):
        """Some functions are documented, some are not — pct should be between 0 and 100."""
        repo = create_fixture_repo(tmp_path)
        agent = RepositoryAnalyzerAgent(llm=_make_mock_llm())

        result = await agent.run({"repo_path": str(repo)})
        pct = result["documented_functions_pct"]
        assert 0.0 <= pct <= 100.0
        # Not all documented (helpers.py has none), not all undocumented
        assert pct > 0.0
        assert pct < 100.0

    @pytest.mark.asyncio
    async def test_languages_json(self, tmp_path):
        """languages field should be a valid JSON string containing 'python'."""
        repo = create_fixture_repo(tmp_path)
        agent = RepositoryAnalyzerAgent(llm=_make_mock_llm())

        result = await agent.run({"repo_path": str(repo)})
        langs = json.loads(result["languages"])
        assert "python" in langs
        assert langs["python"] >= 1

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, tmp_path):
        """When the LLM fails, analyzer should return fallback summary, not raise."""
        from devforge.utils.llm import LLMError
        repo = create_fixture_repo(tmp_path)

        mock_llm = MagicMock()
        mock_llm.call_json = AsyncMock(side_effect=LLMError("API unavailable"))
        agent = RepositoryAnalyzerAgent(llm=mock_llm)

        result = await agent.run({"repo_path": str(repo)})
        # Should still return metrics despite LLM failure
        assert result["file_count"] >= 1
        assert result["analysis_summary"] != ""
        assert json.loads(result["top_issues"]) == []

    @pytest.mark.asyncio
    async def test_invalid_path_raises(self, tmp_path):
        """Analyzer should raise ValueError for non-existent paths."""
        agent = RepositoryAnalyzerAgent(llm=_make_mock_llm())
        with pytest.raises(ValueError, match="does not exist"):
            await agent.run({"repo_path": str(tmp_path / "nonexistent")})
