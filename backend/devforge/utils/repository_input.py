"""Resolve local repository paths and clone supported GitHub URLs safely."""
import configparser
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


class RepositoryInputError(ValueError):
    """Raised when a repository input is invalid or cannot be cloned."""


_GITHUB_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_github_url(value: str) -> str:
    """Return a canonical HTTPS clone URL for a public github.com repository."""
    try:
        parsed = urlsplit(value.strip())
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise RepositoryInputError("Enter a valid GitHub repository URL") from exc

    if (
        parsed.scheme.lower() != "https"
        or host not in {"github.com", "www.github.com"}
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RepositoryInputError("Only HTTPS URLs for github.com repositories are supported")

    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or any(not part or not _GITHUB_SEGMENT.fullmatch(part) for part in parts):
        raise RepositoryInputError("Use a GitHub repository URL in the form https://github.com/owner/repo")

    owner, repository = parts
    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository or owner in {".", ".."} or repository in {".", ".."}:
        raise RepositoryInputError("Enter a valid GitHub owner and repository")
    return f"https://github.com/{owner}/{repository}.git"


def clone_github_repository(value: str) -> Path:
    """Clone one validated GitHub repository into a persistent OS temp workspace."""
    clone_url = validate_github_url(value)
    workspace = Path(tempfile.mkdtemp(prefix="devforge-github-"))
    target = workspace / "repository"
    try:
        subprocess.run(
            ["git", "-c", "credential.helper=", "clone", "--depth", "1", "--", clone_url, str(target)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        # Avoid returning git output, which may contain sensitive environment data.
        raise RepositoryInputError(
            "Could not clone the GitHub repository. Check that it exists and is publicly accessible."
        ) from exc
    return target.resolve()


def resolve_repository_input(value: str) -> Path:
    """Resolve an existing local path or clone an HTTPS GitHub repository URL."""
    source = value.strip()
    if not source:
        raise RepositoryInputError("Repository path or GitHub URL is required")
    if "://" in source or source.lower().startswith("www.github.com/"):
        return clone_github_repository(source)
    return Path(source).expanduser().resolve()


def repository_display_name(value: str, resolved_path: str | Path | None = None) -> str:
    """Return a human-readable repository name independent of clone folder names."""
    source = value.strip()
    if "://" in source or source.lower().startswith("www.github.com/"):
        clone_url = validate_github_url(source)
        name = urlsplit(clone_url).path.rstrip("/").rsplit("/", 1)[-1]
        return name[:-4] if name.lower().endswith(".git") else name
    path = Path(resolved_path).expanduser() if resolved_path is not None else Path(source).expanduser()
    name = path.resolve().name
    return name or "repository"


def canonical_github_url(value: str) -> str | None:
    """Return a stable public source identifier for GitHub inputs."""
    source = value.strip()
    if "://" not in source and not source.lower().startswith("www.github.com/"):
        return None
    canonical = validate_github_url(source)
    parsed = urlsplit(canonical)
    return f"https://github.com{parsed.path.lower()}"


def github_origin_from_clone(path: str | Path) -> str | None:
    """Read and normalize an existing clone's origin without invoking Git or network."""
    config_path = Path(path) / ".git" / "config"
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
        origin = parser.get('remote "origin"', "url", fallback=None)
        if not origin:
            return None
        return canonical_github_url(origin)
    except (OSError, configparser.Error, RepositoryInputError):
        return None
