"""LLM backed, mission-scoped source file implementer."""
import difflib
import ast
import hashlib
from pathlib import Path

from devforge.agents.base import BaseAgent
from devforge.utils.llm import LLMError

EDITABLE_SUFFIXES = {".py", ".toml", ".txt", ".yaml", ".yml", ".json"}


class ImplementerAgent(BaseAgent):
    name = "implementer"

    def __init__(self, llm, emit):
        super().__init__()
        self.llm = llm
        self.emit = emit

    @staticmethod
    def _local_test_fallback(root: Path, relative: str) -> str:
        """Create executable pytest smoke tests when the LLM provider is unavailable."""
        source_name = Path(relative).name
        source_path = root / source_name
        if not source_path.is_file():
            raise ValueError("target_missing_or_outside_repository")
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        functions = [
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]
        classes = [
            node.name for node in tree.body
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
        ]
        module = source_path.stem
        lines = [
            '"""Local fallback tests generated when the configured LLM is unavailable."""',
            "",
            "import importlib",
            "",
            "",
            "MODULE = importlib.import_module(" + repr(module) + ")",
            "",
        ]
        for name in functions:
            lines.extend([
                "def test_" + name + "_is_available():",
                "    assert callable(getattr(MODULE, " + repr(name) + "))",
                "",
            ])
        for name in classes:
            lines.extend([
                "def test_" + name + "_is_available():",
                "    assert isinstance(getattr(MODULE, " + repr(name) + "), type)",
                "",
            ])
        if not functions and not classes:
            lines.extend(["def test_module_imports():", "    assert MODULE is not None", ""])
        return "\n".join(lines) + "\n"

    async def run(self, context: dict) -> dict:
        root = Path(context["repo_path"]).resolve()
        file_changes: dict[str, dict] = {}

        async def update_file(relative: str) -> tuple[str | None, dict | None]:
            filename = Path(str(relative)).name or "unknown file"
            retry = bool(context.get("retry_mode"))
            started_event = "file_retry_started" if retry else "started"
            completed_event = "file_retry_completed" if retry else "completed"
            failed_event = "file_retry_failed" if retry else "failed"
            await self.emit("implementer", started_event, f"Preparing mission change for {filename}", str(relative))
            try:
                target = (root / relative).resolve()
                if not target.is_relative_to(root):
                    raise ValueError("target_missing_or_outside_repository")
                relative_text = str(relative).replace(chr(92), "/")
                is_new_test = (
                    context.get("mission_type") == "test_coverage"
                    and relative_text.startswith("tests/")
                    and target.suffix.lower() == ".py"
                )
                if target.exists() and not target.is_file():
                    raise ValueError("target_missing_or_outside_repository")
                if not target.exists() and not is_new_test:
                    raise ValueError("target_missing_or_outside_repository")
                if target.suffix.lower() not in EDITABLE_SUFFIXES:
                    raise ValueError("unsupported_file_type")
                original = target.read_text(encoding="utf-8") if target.exists() else ""
                system_prompt = (
                    "You are a careful Python engineer. Return only the complete updated file contents. "
                    "Preserve unrelated behavior and do not include markdown fences."
                )
                if is_new_test and not original:
                    system_prompt += (
                        " This is a new pytest file. Create focused tests for the referenced repository module; "
                        "do not place test code into production modules."
                    )
                used_local_fallback = False
                try:
                    text = await self.llm.call_text(
                        system_prompt,
                        f"Mission: {context['title']}\nProblem: {context['problem']}\n"
                        f"Repository relative path: {relative}\nCurrent file:\n{original}",
                    )
                except LLMError:
                    if not is_new_test:
                        raise
                    text = self._local_test_fallback(root, relative)
                    used_local_fallback = True
                text = text.strip()
                if text.startswith("```") or not text or text == original.strip():
                    raise ValueError("no_usable_changed_content")
                if not text.endswith("\n"):
                    text += "\n"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                diff = list(difflib.unified_diff(
                    original.splitlines(), text.splitlines(), lineterm="",
                ))
                file_changes[relative] = {
                    "path": relative,
                    "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "after_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "lines_added": sum(1 for line in diff if line.startswith("+") and not line.startswith("+++")),
                    "lines_deleted": sum(1 for line in diff if line.startswith("-") and not line.startswith("---")),
                }
                event_message = (
                    "Created executable local fallback tests"
                    if used_local_fallback
                    else ("Created new test file from LLM output" if is_new_test and not original else "Updated file from LLM output")
                )
                await self.emit("implementer", completed_event, event_message, str(relative))
                return str(relative), None
            except Exception as exc:  # noqa: BLE001 - turn per-file errors into persisted checkpoints
                known_categories = {
                    "target_missing_or_outside_repository", "unsupported_file_type",
                    "no_usable_changed_content",
                }
                if type(exc).__name__ == "LLMError":
                    category = "provider_error"
                    detail = "The provider could not complete this file update."
                elif isinstance(exc, ValueError) and str(exc) in known_categories:
                    category = str(exc)
                    detail = {
                        "target_missing_or_outside_repository": "The target is missing or outside the repository.",
                        "unsupported_file_type": "The target file type is not supported.",
                        "no_usable_changed_content": "No usable changed file content was returned.",
                    }[category]
                else:
                    category = "update_error"
                    detail = f"The file update failed ({type(exc).__name__})."
                reason = f"Could not update {filename}: {detail}"
                await self.emit("implementer", failed_event, reason, str(relative))
                return None, {"filename": str(relative), "agent": "implementer", "stage": "implementer",
                              "category": category, "reason": reason}

        changed: list[str] = []
        failures: list[dict] = []
        for path in dict.fromkeys(context["files"]):
            completed, failure = await update_file(path)
            if completed:
                changed.append(completed)
            if failure:
                failures.append(failure)
                # Preserve mission ordering: later targets remain not started and are resumed later.
                break
        return {"changed_files": changed, "file_changes": list(file_changes.values()),
                "failures": failures}
