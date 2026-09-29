"""Safety and execution-flow tests for documentation missions."""
import asyncio

import pytest

from devforge.agents.documenter import (
    DocumenterAgent,
    DocumenterFailure,
    apply_python_documentation,
)
from devforge.agents.orchestrator import AgentOrchestrator


class QueueLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def call_text(self, _system_prompt, _user_prompt):
        self.calls += 1
        return self.outputs.pop(0)


def _context(root, files):
    return {
        "repo_path": str(root), "files": files,
        "title": "Improve documentation", "problem": "Document public functions.",
    }


def test_missing_later_target_fails_before_any_file_is_modified(tmp_path):
    first = tmp_path / "README.md"
    first.write_text("# Original\n", encoding="utf-8")
    events = []
    llm = QueueLLM(["# Updated\n"])

    async def emit(agent, event_type, message, target_file=None):
        events.append((agent, event_type, message, target_file))

    with pytest.raises(DocumenterFailure, match="missing.md"):
        asyncio.run(DocumenterAgent(llm, emit).run(_context(tmp_path, ["README.md", "missing.md"])))

    assert first.read_text(encoding="utf-8") == "# Original\n"
    assert llm.calls == 0
    assert events == [(
        "documenter", "failed",
        "invalid_target: Target is missing, not a file, or outside the repository.", "missing.md",
    )]


def test_target_outside_repository_is_rejected_before_writing(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    inside = root / "README.md"
    inside.write_text("# Original\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    llm = QueueLLM(["# Changed\n"])

    async def emit(*_args):
        pass

    with pytest.raises(DocumenterFailure, match="outside.md"):
        asyncio.run(DocumenterAgent(llm, emit).run(_context(root, ["README.md", "../outside.md"])))

    assert inside.read_text(encoding="utf-8") == "# Original\n"
    assert outside.read_text(encoding="utf-8") == "# Outside\n"
    assert llm.calls == 0


def test_valid_multifile_documentation_mission_completes_all_targets(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "guide.rst").write_text("Guide\n=====\n", encoding="utf-8")
    events = []
    llm = QueueLLM(["# Project\n\nUsage details.\n", "Guide\n=====\n\nHow to use it.\n"])

    async def emit(agent, event_type, message, target_file=None):
        events.append((agent, event_type, message, target_file))

    result = asyncio.run(DocumenterAgent(llm, emit).run(
        _context(tmp_path, ["README.md", "guide.rst"]),
    ))

    assert result["changed_files"] == ["README.md", "guide.rst"]
    assert len(result["file_changes"]) == 2
    assert "Usage details." in (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "How to use it." in (tmp_path / "guide.rst").read_text(encoding="utf-8")
    assert events[-1] == ("documenter", "completed", "Documentation mission completed", None)


def test_python_documentation_preserves_all_source_outside_docstrings(tmp_path):
    original = (
        "# Keep this comment\n"
        "import math\n\n"
        "def calculate(value):\n"
        "    result = value * 2\n"
        "    return result\n"
    )
    generated = (
        "# Keep this comment\n"
        "import math\n\n"
        "def calculate(value):\n"
        '    """Double the input value."""\n'
        "    result = value * 2\n"
        "    return result\n"
    )
    expected = original.replace("    result = value * 2\n", "    'Double the input value.'\n    result = value * 2\n")

    updated = apply_python_documentation(original, generated)
    assert updated == expected


def test_python_output_that_changes_code_is_rejected_without_write(tmp_path):
    source = "def calculate(value):\n    return value * 2\n"
    file = tmp_path / "module.py"
    file.write_text(source, encoding="utf-8")
    generated = 'def calculate(value):\n    """Double the input."""\n    return value * 3\n'
    events = []

    async def emit(agent, event_type, message, target_file=None):
        events.append((agent, event_type, message, target_file))

    with pytest.raises(DocumenterFailure, match="unsafe_python_output"):
        asyncio.run(DocumenterAgent(QueueLLM([generated]), emit).run(_context(tmp_path, ["module.py"])))

    assert file.read_text(encoding="utf-8") == source
    assert events[-1][0:2] == ("documenter", "failed")
    assert events[-1][2].startswith("unsafe_python_output:")


def test_successful_documenter_runs_tester_and_real_verification(tmp_path):
    (tmp_path / "module.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (tmp_path / "test_module.py").write_text(
        "from module import value\n\n\ndef test_value():\n    assert value() == 1\n",
        encoding="utf-8",
    )
    generated = 'def value():\n    """Return the stable value."""\n    return 1\n'
    events = []

    async def emit(agent, event_type, message, target_file=None):
        events.append((agent, event_type, message, target_file))

    result = asyncio.run(AgentOrchestrator(QueueLLM([generated]), emit).run({
        "title": "Document value", "problem": "Add a function docstring.",
        "mission_type": "documentation", "affected_files": ["module.py"],
    }, str(tmp_path)))

    assert result["verification"]["passed"] is True
    assert result["verification"]["pass_count"] == 1
    assert [event[:2] for event in events][-2:] == [
        ("tester", "started"), ("tester", "completed"),
    ]
    assert any(event[2] == "Documentation mission completed" for event in events)
