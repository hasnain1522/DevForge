"""Per-execution repository copies and sanitized ZIP delivery artifacts."""
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".tox", ".devforge", ".ssh",
}
_SKIP_FILES = {
    ".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json",
    "id_rsa", "id_ed25519",
}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
_SECRET_ASSIGNMENT = re.compile(
    r"(?im)(?P<prefix>(?:[\"']?)(?:api[_-]?key|openrouter[_-]?key|auth[_-]?secret|"
    r"client[_-]?secret|access[_-]?token|refresh[_-]?token|password|passwd|secret|token)"
    r"(?:[\"']?)\s*[:=]\s*)(?P<quote>[\"'])(?P<value>[^\"'\r\n]*)(?P=quote)"
)
_SECRET_MAPPING = re.compile(
    r"(?im)(?P<prefix>^\s*[\"']?(?:api[_-]?key|openrouter[_-]?key|auth[_-]?secret|"
    r"client[_-]?secret|access[_-]?token|refresh[_-]?token|password|passwd|secret|token)"
    r"[\"']?\s*:\s*)(?![\"'])(?P<value>[^\s,#}\]]+)"
)
_SECRET_CONFIG_ASSIGNMENT = re.compile(
    r"(?im)(?P<prefix>^\s*(?:api[_-]?key|openrouter[_-]?key|auth[_-]?secret|"
    r"client[_-]?secret|access[_-]?token|refresh[_-]?token|password|passwd|secret|token)"
    r"\s*=\s*)(?![\"'])(?P<value>[^\s#]+)"
)
_TOKEN_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}={0,2}"),
)
_PLACEHOLDERS = {"", "your-api-key", "replace-me", "replace-with-a-secret", "changeme", "example"}


@dataclass(frozen=True)
class ArtifactPackage:
    filename: str
    path: Path
    size_bytes: int
    created_at: datetime


def should_exclude_path(path: Path, *, is_directory: bool = False) -> bool:
    """Identify secret-bearing and generated repository content to omit."""
    name = path.name.lower()
    if name.startswith(".env"):
        return True
    if name in _SKIP_DIRS or name in _SKIP_FILES:
        return True
    if name.startswith(".devforge"):
        return True
    if is_directory:
        return False
    return name.endswith((".pyc", ".pyo")) or path.suffix.lower() in _SECRET_SUFFIXES


def _ignore_copy_entries(directory: str, names: list[str]) -> set[str]:
    parent = Path(directory)
    ignored = set()
    for name in names:
        entry = parent / name
        if should_exclude_path(entry, is_directory=entry.is_dir()):
            ignored.add(name)
    return ignored


def create_execution_copy(source_path: str, execution_id: str) -> Path:
    """Create a unique copy; all subsequent agent writes are confined to it."""
    source = Path(source_path).resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Repository source is not a directory")
    workspace_root = execution_workspace_root()
    workspace_root.mkdir(parents=True, exist_ok=True)
    destination = (workspace_root / execution_id).resolve()
    if not destination.is_relative_to(workspace_root.resolve()):
        raise ValueError("Invalid execution workspace identifier")
    shutil.copytree(source, destination, symlinks=True, ignore=_ignore_copy_entries)
    return destination


def execution_workspace_root() -> Path:
    """Return the trusted parent directory for isolated execution workspaces."""
    return (Path(tempfile.gettempdir()) / "devforge-execution-workspaces").resolve()


def execution_workspace_path(execution_id: str) -> Path:
    """Resolve an execution's deterministic workspace path under the trusted root."""
    root = execution_workspace_root()
    workspace = (root / execution_id).resolve()
    if not workspace.is_relative_to(root):
        raise ValueError("Invalid execution workspace identifier")
    return workspace


def _safe_repo_name(repository_name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(repository_name).name).strip(".-_")
    return name or "repository"


def _safe_text(data: bytes) -> bytes | None:
    if b"-----BEGIN " in data and b"PRIVATE KEY-----" in data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Arbitrary binary project assets are retained unless they resemble key material.
        if any(pattern.search(data.decode("latin-1")) for pattern in _TOKEN_PATTERNS):
            return None
        return data
    if "\x00" in text:
        return data

    def redact_assignment(match: re.Match[str]) -> str:
        value = match.group("value")
        if value.strip().lower() in _PLACEHOLDERS or value.strip().startswith(("${", "<")):
            return match.group(0)
        return f"{match.group('prefix')}{match.group('quote')}[REDACTED]{match.group('quote')}"

    def redact_unquoted(match: re.Match[str]) -> str:
        value = match.group("value")
        if value.strip().lower() in _PLACEHOLDERS or value.strip().startswith(("${", "<")):
            return match.group(0)
        return f"{match.group('prefix')}[REDACTED]"

    text = _SECRET_ASSIGNMENT.sub(redact_assignment, text)
    text = _SECRET_MAPPING.sub(redact_unquoted, text)
    text = _SECRET_CONFIG_ASSIGNMENT.sub(redact_unquoted, text)
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text.encode("utf-8")


def create_repository_zip(workspace: str | Path, repository_name: str, execution_id: str) -> ArtifactPackage:
    """Package the modified execution copy, excluding secrets and internal files."""
    root = Path(workspace).resolve(strict=True)
    artifact_root = Path(tempfile.gettempdir()) / "devforge-deliveries"
    artifact_root.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_repo_name(repository_name)}-polished-{execution_id[:8]}.zip"
    archive_path = artifact_root / f"{execution_id}-{filename}"
    temporary_path = archive_path.with_suffix(".zip.tmp")
    archive_root = _safe_repo_name(repository_name)

    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{archive_root}/", "")
            for directory, dirnames, filenames in os.walk(root, followlinks=False):
                directory_path = Path(directory)
                dirnames[:] = sorted(
                    name for name in dirnames
                    if not should_exclude_path(directory_path / name, is_directory=True)
                    and not (directory_path / name).is_symlink()
                )
                for name in sorted(dirnames):
                    relative_dir = (directory_path / name).relative_to(root)
                    archive.writestr(f"{archive_root}/{relative_dir.as_posix()}/", "")
                for name in sorted(filenames):
                    target = directory_path / name
                    if target.is_symlink() or should_exclude_path(target):
                        continue
                    data = _safe_text(target.read_bytes())
                    if data is None:
                        continue
                    relative = target.relative_to(root)
                    archive.writestr(f"{archive_root}/{relative.as_posix()}", data)
        os.replace(temporary_path, archive_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        raise

    return ArtifactPackage(
        filename=filename,
        path=archive_path,
        size_bytes=archive_path.stat().st_size,
        created_at=datetime.now(UTC),
    )


def artifact_storage_root() -> Path:
    """Return the trusted root used for generated delivery ZIPs."""
    return (Path(tempfile.gettempdir()) / "devforge-deliveries").resolve()
