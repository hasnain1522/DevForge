"""Isolated execution workspace and ZIP sanitization tests."""
import uuid
from zipfile import ZipFile

from devforge.utils.delivery import create_execution_copy, create_repository_zip


def test_each_run_gets_a_distinct_copy_and_zip_contains_only_safe_project_files(tmp_path):
    source = tmp_path / "source-project"
    (source / "src").mkdir(parents=True)
    (source / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "README.md").write_text("Project guide\n", encoding="utf-8")
    (source / ".env").write_text("OPENROUTER_API_KEY=env-secret-marker\n", encoding="utf-8")
    (source / "settings.yaml").write_text("api_key: yaml-secret-marker\n", encoding="utf-8")
    (source / "node_modules" / "package").mkdir(parents=True)
    (source / "node_modules" / "package" / "index.js").write_text("vendor", encoding="utf-8")
    (source / "src" / "__pycache__").mkdir()
    (source / "src" / "__pycache__" / "app.pyc").write_bytes(b"bytecode")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("repository metadata", encoding="utf-8")
    (source / ".devforge").mkdir()
    (source / ".devforge" / "run.json").write_text("internal", encoding="utf-8")

    first_id = f"delivery-test-{uuid.uuid4().hex}"
    second_id = f"delivery-test-{uuid.uuid4().hex}"
    first = create_execution_copy(str(source), first_id)
    second = create_execution_copy(str(source), second_id)
    assert first != second
    assert first != source.resolve()
    assert not (first / ".env").exists()
    (first / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert (source / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (second / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    package = create_repository_zip(first, "source-project", first_id)
    with ZipFile(package.path) as archive:
        names = set(archive.namelist())
        assert "source-project/README.md" in names
        assert "source-project/src/app.py" in names
        assert not any(".env" in name for name in names)
        assert not any("node_modules" in name for name in names)
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        assert not any(".git/" in name or ".devforge" in name for name in names)
        contents = b"".join(archive.read(name) for name in names if not name.endswith("/"))
        assert b"yaml-secret-marker" not in contents
        assert b"env-secret-marker" not in contents
        assert b"VALUE = 2" in contents
