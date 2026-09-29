"""Update only explicitly selected documentation files."""
import ast
import difflib
import hashlib
import os
import stat
import tempfile
from pathlib import Path

from devforge.agents.base import BaseAgent


class DocumenterFailure(RuntimeError):
    """Safe, actionable documenter failure with no provider output attached."""

    def __init__(self, filename: str, category: str, reason: str) -> None:
        self.filename = Path(filename).name or "unknown file"
        self.category = category
        self.reason = reason
        super().__init__(f"Documentation failed for {self.filename} ({category}): {reason}")


class UnsafePythonDocumentation(ValueError):
    """Generated Python differs outside safely replaceable docstrings."""


_SUPPORTED_SUFFIXES = {".md", ".rst", ".py"}
_DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstring_expression(owner: ast.AST) -> ast.Expr | None:
    body = getattr(owner, "body", None)
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return body[0]
    return None


def _without_docstrings(tree: ast.AST) -> str:
    """Return a structural AST dump with module/class/function docstrings removed."""
    for node in ast.walk(tree):
        if isinstance(node, _DOCSTRING_OWNERS) and _docstring_expression(node):
            node.body = node.body[1:]
    return ast.dump(tree, include_attributes=False)


def _source_offset(source: str, line_number: int, utf8_column: int) -> int:
    lines = source.splitlines(keepends=True)
    prefix = lines[line_number - 1].encode("utf-8")[:utf8_column].decode("utf-8")
    return sum(len(line) for line in lines[: line_number - 1]) + len(prefix)


def _atomic_write(target: Path, content: str) -> None:
    """Replace one file atomically while retaining its existing permission bits."""
    descriptor, temporary_name = tempfile.mkstemp(prefix=".devforge-doc-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output_file:
            output_file.write(content)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.chmod(temporary_name, stat.S_IMODE(target.stat().st_mode))
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def apply_python_documentation(original: str, generated: str) -> str:
    """Apply generated docstrings while preserving every other source character."""
    try:
        original_tree = ast.parse(original)
        generated_tree = ast.parse(generated)
    except SyntaxError as exc:
        raise UnsafePythonDocumentation("invalid Python output") from exc

    if _without_docstrings(ast.parse(original)) != _without_docstrings(ast.parse(generated)):
        raise UnsafePythonDocumentation("non-documentation Python syntax changed")

    original_owners = [node for node in ast.walk(original_tree) if isinstance(node, _DOCSTRING_OWNERS)]
    generated_owners = [node for node in ast.walk(generated_tree) if isinstance(node, _DOCSTRING_OWNERS)]
    if len(original_owners) != len(generated_owners):
        raise UnsafePythonDocumentation("documentation owners do not match")

    replacements: list[tuple[int, int, str]] = []
    newline = "\r\n" if "\r\n" in original else "\n"
    for old_owner, new_owner in zip(original_owners, generated_owners, strict=True):
        if type(old_owner) is not type(new_owner):
            raise UnsafePythonDocumentation("documentation owners do not match")
        if getattr(old_owner, "name", None) != getattr(new_owner, "name", None):
            raise UnsafePythonDocumentation("documentation owners do not match")

        old_expr = _docstring_expression(old_owner)
        new_expr = _docstring_expression(new_owner)
        if new_expr is None:
            if old_expr is not None:
                raise UnsafePythonDocumentation("generated output removed an existing docstring")
            continue

        rendered = repr(new_expr.value.value)
        if old_expr is not None:
            start = _source_offset(original, old_expr.lineno, old_expr.col_offset)
            end = _source_offset(original, old_expr.end_lineno, old_expr.end_col_offset)
            replacements.append((start, end, rendered))
            continue

        old_body = getattr(old_owner, "body", [])
        owner_line = getattr(old_owner, "lineno", None)
        if not old_body or old_body[0].lineno == owner_line:
            raise UnsafePythonDocumentation("cannot safely insert a docstring into this layout")
        lines = original.splitlines(keepends=True)
        first_statement = old_body[0]
        line = lines[first_statement.lineno - 1]
        indent = line[: len(line) - len(line.lstrip(" \t"))]
        start = sum(len(part) for part in lines[: first_statement.lineno - 1])
        replacements.append((start, start, f"{indent}{rendered}{newline}"))

    updated = original
    for start, end, content in sorted(replacements, reverse=True):
        updated = updated[:start] + content + updated[end:]
    if updated == original:
        raise UnsafePythonDocumentation("generated output contained no safe documentation changes")
    return updated


class DocumenterAgent(BaseAgent):
    name = "documenter"

    def __init__(self, llm, emit):
        super().__init__()
        self.llm = llm
        self.emit = emit

    async def _fail(self, filename: str, category: str, reason: str) -> DocumenterFailure:
        safe_name = Path(str(filename)).as_posix() or "unknown file"
        await self.emit("documenter", "failed", f"{category}: {reason}", safe_name)
        return DocumenterFailure(safe_name, category, reason)

    async def run(self, context: dict) -> dict:
        root = Path(context["repo_path"]).resolve()
        selected = list(dict.fromkeys(context["files"]))
        if not selected:
            raise await self._fail("repository", "invalid_targets", "No documentation targets were selected.")

        targets: list[tuple[str, Path]] = []
        # Validate every target before calling the provider or changing file contents.
        for relative in selected:
            filename = str(relative)
            try:
                candidate = (root / filename).resolve(strict=True)
                valid = candidate.is_relative_to(root) and candidate.is_file()
            except (OSError, RuntimeError, TypeError, ValueError):
                valid = False
                candidate = root
            if not valid:
                raise await self._fail(
                    filename, "invalid_target", "Target is missing, not a file, or outside the repository.",
                )
            if candidate.suffix.lower() not in _SUPPORTED_SUFFIXES:
                raise await self._fail(
                    filename, "unsupported_file", "Target is not a Markdown, reStructuredText, or Python file.",
                )
            targets.append((filename, candidate))

        staged: list[tuple[str, Path, str, str]] = []
        for relative, target in targets:
            filename = Path(relative).name
            await self.emit("documenter", "started", f"Updating {filename}", filename)
            try:
                with target.open("r", encoding="utf-8", newline="") as source_file:
                    original = source_file.read()
                prompt = (
                    "Update only documentation relevant to the stated mission. Return the complete "
                    "updated document, without markdown fences; preserve unrelated sections."
                )
                if target.suffix.lower() == ".py":
                    prompt = (
                        "Return the complete Python file with only module, class, or function docstrings "
                        "added or improved. Do not change imports, statements, signatures, formatting, or "
                        "any source outside docstring expressions. No markdown fences."
                    )
                generated = await self.llm.call_text(
                    prompt,
                    f"Mission: {context['title']}\nProblem: {context['problem']}\n"
                    f"File: {filename}\nCurrent document:\n{original}",
                )
                if target.suffix.lower() == ".py":
                    updated = apply_python_documentation(original, generated)
                else:
                    updated = generated.strip()
                    if not updated or updated.startswith("```") or updated == original.strip():
                        raise ValueError("No usable documentation change was returned.")
                    if not updated.endswith(("\n", "\r")):
                        updated += "\n"
                staged.append((relative, target, original, updated))
            except UnsafePythonDocumentation:
                raise await self._fail(
                    relative, "unsafe_python_output",
                    "Generated output changed code outside docstrings or could not be applied safely.",
                )
            except Exception as exc:
                is_provider_error = type(exc).__name__ == "LLMError"
                category = "provider_error" if is_provider_error else "update_error"
                reason = (
                    "Documentation provider could not complete the update."
                    if is_provider_error else "Documentation could not be safely prepared."
                )
                raise await self._fail(relative, category, reason) from exc

        # Do not write any file until all provider outputs are safely staged.
        written: list[tuple[Path, str]] = []
        active_relative = "repository"
        try:
            for active_relative, target, original, updated in staged:
                _atomic_write(target, updated)
                written.append((target, original))
        except OSError as exc:
            for target, original in reversed(written):
                try:
                    _atomic_write(target, original)
                except OSError:
                    pass
            raise await self._fail(
                active_relative, "write_error", "Documentation could not be saved; prior writes were reverted.",
            ) from exc

        file_changes = []
        changed = []
        for relative, _target, original, updated in staged:
            if original == updated:
                continue
            diff = list(difflib.unified_diff(original.splitlines(), updated.splitlines(), lineterm=""))
            file_changes.append({
                "path": relative,
                "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "after_sha256": hashlib.sha256(updated.encode()).hexdigest(),
                "lines_added": sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")),
                "lines_deleted": sum(1 for line in diff if line.startswith("-") and not line.startswith("---")),
            })
            changed.append(relative)
            await self.emit("documenter", "completed", "Updated documentation", relative)

        await self.emit("documenter", "completed", "Documentation mission completed")
        return {"changed_files": changed, "file_changes": file_changes}
