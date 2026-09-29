"""GitHub repository URL validation and isolated clone tests."""
import subprocess
from pathlib import Path

import pytest

from devforge.utils.repository_input import (
    RepositoryInputError,
    canonical_github_url,
    clone_github_repository,
    repository_display_name,
    resolve_repository_input,
    validate_github_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/owner/project", "https://github.com/owner/project.git"),
        ("https://github.com/owner/project.git", "https://github.com/owner/project.git"),
        ("https://www.github.com/owner/project/", "https://github.com/owner/project.git"),
    ],
)
def test_validate_github_repository_url(value, expected):
    assert validate_github_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/owner/project",
        "https://github.com.evil.example/owner/project",
        "https://user:password@github.com/owner/project",
        "https://github.com/owner/project/tree/main",
        "https://github.com/owner/project?tab=readme",
        "ssh://git@github.com/owner/project.git",
    ],
)
def test_validate_rejects_unsupported_repository_urls(value):
    with pytest.raises(RepositoryInputError):
        validate_github_url(value)


def test_clone_github_repository_uses_isolated_temp_workspace(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        target = Path(command[-1])
        target.mkdir(parents=True)
        (target / "README.md").write_text("fixture", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("devforge.utils.repository_input.subprocess.run", fake_run)
    monkeypatch.setattr("devforge.utils.repository_input.tempfile.mkdtemp", lambda **_: str(tmp_path / "isolated"))

    cloned = clone_github_repository("https://github.com/owner/project")

    assert cloned == (tmp_path / "isolated" / "repository").resolve()
    assert (cloned / "README.md").read_text(encoding="utf-8") == "fixture"
    assert calls[0][0][0:5] == ["git", "-c", "credential.helper=", "clone", "--depth"]
    assert "https://github.com/owner/project.git" in calls[0][0]
    assert calls[0][1]["timeout"] == 180


def test_local_repository_path_remains_supported(tmp_path):
    assert resolve_repository_input(str(tmp_path)) == tmp_path.resolve()


def test_github_repository_display_name_strips_git_suffix():
    url = "https://github.com/hasnain1522/CareerGuide-AI.git"
    assert repository_display_name(url, Path("repository")) == "CareerGuide-AI"
    assert repository_display_name("https://github.com/owner/AI-Career-Agent", Path("repository")) == "AI-Career-Agent"
    assert canonical_github_url(url) == "https://github.com/hasnain1522/careerguide-ai.git"


def test_local_repository_display_name_uses_folder_name(tmp_path):
    project = tmp_path / "AI-Career-Agent"
    project.mkdir()
    assert repository_display_name(str(project), project) == "AI-Career-Agent"
