"""
File tree utilities for repository analysis (Phase 2+).

Phase 1: structure and constants in place; walk function ready for Phase 2.
"""
import os
from pathlib import Path

# Directories to skip entirely when walking a repository
SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    ".tox",
})

# Maximum source files to ingest (protects against very large repos)
FILE_CAP = 200

# Python source file extensions
PYTHON_EXTENSIONS: frozenset[str] = frozenset({".py"})


def walk_repository(repo_path: str) -> list[str]:
    """
    Walk a repository and return a list of source file paths (relative to repo_path).

    Skips SKIP_DIRS directories. Caps at FILE_CAP files with a logged warning.
    Used by RepositoryAnalyzerAgent (Phase 2).
    """
    import logging
    logger = logging.getLogger(__name__)

    root = Path(repo_path).resolve()
    collected: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip directories in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(root))
            collected.append(rel_path)

            if len(collected) >= FILE_CAP:
                logger.warning(
                    "Repository has more than %d files; truncating file list.", FILE_CAP
                )
                return collected

    return collected


def detect_languages(file_paths: list[str]) -> dict[str, int]:
    """
    Count files per language based on file extension.

    Returns a dict like {"python": 12, "markdown": 3}.
    MVP: primarily detects Python. Other extensions are grouped generically.
    """
    extension_map: dict[str, str] = {
        ".py": "python",
        ".md": "markdown",
        ".txt": "text",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
        ".sh": "shell",
    }
    counts: dict[str, int] = {}
    for path in file_paths:
        ext = Path(path).suffix.lower()
        lang = extension_map.get(ext, "other")
        counts[lang] = counts.get(lang, 0) + 1
    return counts
