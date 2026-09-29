"""Regression tests for isolated test-file creation."""

import asyncio
from pathlib import Path

from devforge.agents.implementer import ImplementerAgent


class TestFileLLM:
    async def call_text(self, _system_prompt: str, user_prompt: str) -> str:
        filename = user_prompt.split("Repository relative path: ", 1)[1].splitlines()[0]
        module = Path(filename).stem.removeprefix("test_")
        return f"from {module} import value\n\n\ndef test_value():\n    assert value() == 2\n"


def test_coverage_implementer_creates_missing_test_file(tmp_path):
    (tmp_path / "app.py").write_text(
        "def value():\n    return 2\n",
        encoding="utf-8",
    )
    events = []

    async def emit(agent, event_type, message, target_file=None):
        events.append((agent, event_type, message, target_file))

    result = asyncio.run(
        ImplementerAgent(TestFileLLM(), emit).run(
            {
                "repo_path": str(tmp_path),
                "mission_type": "test_coverage",
                "title": "Create tests",
                "problem": "Add tests for app.py",
                "files": ["tests/test_app.py"],
            }
        )
    )

    assert result["failures"] == []
    assert result["changed_files"] == ["tests/test_app.py"]
    assert (tmp_path / "tests/test_app.py").is_file()
    assert "Created new test file" in events[-1][2]
