"""
Minimal Python fixture repository for Phase 2 tests.

This module creates a temporary Python project with:
- A few source files with known characteristics
- Some test files
- Some TODO/FIXME comments
- Some undocumented functions
- Lint errors (via ruff)

Used by test_analyzer.py and test_missions.py.
"""
import textwrap
from pathlib import Path


def create_fixture_repo(tmp_path: Path) -> Path:
    """
    Create a small Python repository under tmp_path with predictable properties.

    Expected metrics:
        file_count          = 6 (.py files)
        test_file_count     = 2 (test_auth.py, test_utils.py)
        test_function_count = 3 (test_validate_email, test_hash_password, test_format_name)
        todo_count          = 3 (2 TODOs + 1 FIXME)
        lint_error_count    >= 1 (unused import)
        documented_functions_pct < 100 (some functions lack docstrings)
    """
    root = tmp_path / "sample_repo"
    root.mkdir()

    # pyproject.toml so ruff can run
    (root / "pyproject.toml").write_text(textwrap.dedent("""\
        [project]
        name = "sample"
        version = "0.1.0"

        [tool.ruff]
        line-length = 100
    """))

    # auth/validators.py — source file with mixed documented/undocumented functions
    auth = root / "auth"
    auth.mkdir()
    (auth / "__init__.py").write_text("")
    (auth / "validators.py").write_text(textwrap.dedent("""\
        import re
        import os  # unused import — ruff will flag this

        EMAIL_RE = re.compile(r"[^@]+@[^@]+\\.[^@]+")

        def validate_email(email: str) -> bool:
            \"\"\"Return True if email looks valid.\"\"\"
            return bool(EMAIL_RE.match(email))

        def validate_password(password: str) -> bool:
            # TODO: add complexity requirements
            return len(password) >= 8

        def hash_password(password: str) -> str:
            # FIXME: use a real hashing library
            return password[::-1]
    """))

    # utils/helpers.py — no docstrings
    utils = root / "utils"
    utils.mkdir()
    (utils / "__init__.py").write_text("")
    (utils / "helpers.py").write_text(textwrap.dedent("""\
        def format_name(first: str, last: str) -> str:
            return f"{first} {last}"

        def truncate(text: str, max_len: int = 100) -> str:
            # TODO: add ellipsis option
            return text[:max_len]
    """))

    # tests/test_auth.py
    tests = root / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_auth.py").write_text(textwrap.dedent("""\
        from auth.validators import validate_email, hash_password

        def test_validate_email():
            \"\"\"Valid email addresses should pass validation.\"\"\"
            assert validate_email("user@example.com") is True
            assert validate_email("notanemail") is False

        def test_hash_password():
            result = hash_password("secret")
            assert isinstance(result, str)
    """))

    # tests/test_utils.py
    (tests / "test_utils.py").write_text(textwrap.dedent("""\
        from utils.helpers import format_name

        def test_format_name():
            assert format_name("Ada", "Lovelace") == "Ada Lovelace"
    """))

    return root
