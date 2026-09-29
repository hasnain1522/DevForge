"""Objective repository metrics for before/after execution snapshots."""
import json
from pathlib import Path

from devforge.agents.analyzer import (
    _count_test_functions_in_source,
    _count_todo_in_source,
    _documented_functions_pct,
    _is_test_file,
)
from devforge.utils.file_tree import PYTHON_EXTENSIONS, detect_languages, walk_repository
from devforge.utils.ruff_counter import count_ruff_errors


def capture_metrics(repo_path: str) -> dict:
    root = Path(repo_path).resolve()
    files = walk_repository(str(root))
    python_files = [path for path in files if Path(path).suffix.lower() in PYTHON_EXTENSIONS]
    test_files = sum(_is_test_file(path) for path in python_files)
    test_functions = 0
    todo_count = 0
    documented = 0
    total = 0
    for relative in python_files:
        try:
            source = (root / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        test_functions += _count_test_functions_in_source(source)
        todo_count += _count_todo_in_source(source)
        doc, count = _documented_functions_pct(source)
        documented += doc
        total += count
    lint = count_ruff_errors(str(root))
    return {
        "file_count": len(files),
        "test_file_count": test_files,
        "test_function_count": test_functions,
        "todo_count": todo_count,
        "lint_error_count": lint.error_count,
        "documented_functions_pct": round(documented / total * 100, 1) if total else 0.0,
        "languages": json.dumps(detect_languages(files)),
        "top_issues": "[]",
        "analysis_summary": "Objective metrics captured from repository files and ruff.",
    }
