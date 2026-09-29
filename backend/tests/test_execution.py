"""Phase 3 execution API and repository-boundary tests."""
import io
import json
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from devforge.config import settings
from devforge.db.models import Mission, Repository
from devforge.db.session import engine, init_db
from devforge.main import app


class FakeLLM:
    async def call_text(self, _system_prompt: str, _user_prompt: str) -> str:
        return "def value():\n    return 2\n"


def test_execution_endpoint_runs_mission_verification_and_sse(monkeypatch, tmp_path):
    init_db()
    (tmp_path / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "from app import value\n\n\ndef test_value():\n    assert value() == 2\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("API_KEY=must-not-be-packaged\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("TOKEN=example-secret\n", encoding="utf-8")
    (tmp_path / "config.py").write_text(
        'OPENROUTER_API_KEY = "sk-or-v1-test-secret-value-that-must-not-ship"\n',
        encoding="utf-8",
    )
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("internal", encoding="utf-8")
    (tmp_path / "app" / "__pycache__").mkdir(parents=True)
    (tmp_path / "app" / "__pycache__" / "module.pyc").write_bytes(b"bytecode")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git internals", encoding="utf-8")
    (tmp_path / ".devforge").mkdir()
    (tmp_path / ".devforge" / "internal.json").write_text("internal", encoding="utf-8")
    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")
    monkeypatch.setattr(settings, "llm_api_key", "configured-for-test")
    monkeypatch.setattr("devforge.api.execute.create_llm_client", FakeLLM)
    with TestClient(app) as live_client:
        account = live_client.post("/auth/register", json={
            "email": "execution-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        assert account.status_code == 201
        user_id = account.json()["id"]
        with Session(engine) as session:
            repo = Repository(name="execution fixture", path=str(tmp_path.resolve()), user_id=user_id)
            session.add(repo)
            session.commit()
            session.refresh(repo)
            repo_id = repo.id
            mission = Mission(
                user_id=user_id, repository_id=repo.id, title="Fix value",
                problem="Return the expected value", mission_type="bug_fix",
                affected_files=json.dumps(["app.py"]),
            )
            session.add(mission)
            session.commit()
            session.refresh(mission)
            mission_id = mission.id

        response = live_client.post(f"/execute/{mission_id}")
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]

        deadline = time.monotonic() + 30
        state = live_client.get(f"/execute/{run_id}").json()
        while state["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            state = live_client.get(f"/execute/{run_id}").json()

        assert state["status"] == "completed", state
        assert state["changed_files"] == ["app.py"]
        assert state["verification"]["passed"] is True
        assert state["verification"]["pass_count"] == 1
        assert "tester" in {event["agent_type"] for event in state["events"]}
        stream = live_client.get(f"/execute/{run_id}/stream")
        assert stream.status_code == 200
        assert "text/event-stream" in stream.headers["content-type"]
        assert '"agent_type": "implementer"' in stream.text
        verify = live_client.post(f"/verify/{run_id}")
        assert verify.status_code == 200
        assert verify.json()["passed"] is True
        evidence = live_client.get(f"/evidence?execution_id={run_id}")
        assert evidence.status_code == 200
        assert {item["type"] for item in evidence.json()} >= {
            "FILE_CHANGE", "TEST_RESULT", "LINT_RESULT", "VERIFICATION", "EXECUTION_LOG",
        }
        report = live_client.get(f"/report/{repo_id}")
        assert report.status_code == 200, report.text
        assert report.json()["verification_passed"] is True
        assert report.json()["changed_files"][0]["path"] == "app.py"
        assert (tmp_path / "app.py").read_text(encoding="utf-8") == "def value():\n    return 1\n"
        assert state["artifact"]["status"] == "ready"
        assert state["artifact"]["execution_id"] == run_id
        assert state["artifact"]["size_bytes"] > 0
        assert state["artifact"]["created_at"]
        assert state["artifact"]["filename"].endswith(".zip")
        download = live_client.get(f"/execute/{run_id}/artifact")
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            names = set(archive.namelist())
            assert any(name.endswith("/app.py") for name in names)
            assert any(name.endswith("/test_app.py") for name in names)
            assert not any(".env" in name for name in names)
            assert not any("node_modules" in name for name in names)
            assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
            assert not any(".git/" in name for name in names)
            assert not any(".devforge" in name for name in names)
            contents = b"".join(archive.read(name) for name in names if not name.endswith("/"))
            assert b"must-not-be-packaged" not in contents
            assert b"example-secret" not in contents
            assert b"sk-or-v1-test-secret-value-that-must-not-ship" not in contents
            assert any(b"return 2" in archive.read(name) for name in names if name.endswith("/app.py"))
        report = live_client.get(f"/report/{repo_id}")
        assert report.json()["artifact"]["status"] == "ready"


def test_execute_unknown_mission_returns_404(monkeypatch):
    from devforge.config import settings

    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")
    with TestClient(app) as client:
        client.post("/auth/register", json={
            "email": "unknown-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        response = client.post("/execute/missing-mission")
        assert response.status_code == 404


def test_documenter_failure_is_persisted_with_safe_reason_and_no_verification(monkeypatch, tmp_path):
    init_db()
    original = "def value():\n    return 1\n"
    (tmp_path / "main.py").write_text(original, encoding="utf-8")
    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")

    class ShouldNotCallLLM:
        async def call_text(self, *_args):
            raise AssertionError("preflight must reject before requesting content")

    monkeypatch.setattr("devforge.api.execute.create_llm_client", ShouldNotCallLLM)
    with TestClient(app) as live_client:
        account = live_client.post("/auth/register", json={
            "email": "doc-failure-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        assert account.status_code == 201
        user_id = account.json()["id"]
        with Session(engine) as session:
            repo = Repository(name="documenter fixture", path=str(tmp_path.resolve()), user_id=user_id)
            session.add(repo)
            session.commit()
            session.refresh(repo)
            mission = Mission(
                user_id=user_id, repository_id=repo.id, title="Document values",
                problem="Document the selected Python files.", mission_type="documentation",
                affected_files=json.dumps(["main.py", "missing.py"]),
            )
            session.add(mission)
            session.commit()
            session.refresh(mission)
            mission_id = mission.id
            repo_id = repo.id

        started = live_client.post(f"/execute/{mission_id}")
        assert started.status_code == 202, started.text
        run_id = started.json()["run_id"]
        deadline = time.monotonic() + 30
        state = live_client.get(f"/execute/{run_id}").json()
        while state["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            state = live_client.get(f"/execute/{run_id}").json()

        assert state["status"] == "failed"
        assert state["verification"] is None
        assert state["artifact"]["status"] == "failed"
        assert live_client.get(f"/execute/{run_id}/artifact").status_code == 404
        assert (tmp_path / "main.py").read_text(encoding="utf-8") == original
        failures = [event for event in state["events"] if event["event_type"] == "failed"]
        assert any(
            event["agent_type"] == "documenter"
            and event["target_file"] == "missing.py"
            and "invalid_target" in event["message"]
            for event in failures
        )
        assert any(
            event["agent_type"] == "orchestrator"
            and "missing.py" in event["message"]
            and "invalid_target" in event["message"]
            for event in failures
        )
        stream = live_client.get(f"/execute/{run_id}/stream")
        assert '"agent_type": "documenter"' in stream.text
        evidence = live_client.get(f"/evidence?execution_id={run_id}")
        assert evidence.status_code == 200
        assert "EXECUTION_LOG" in {item["type"] for item in evidence.json()}
        execution_log = next(item for item in evidence.json() if item["type"] == "EXECUTION_LOG")
        assert any(
            event["agent"] == "documenter" and event["status"] == "failed"
            and "invalid_target" in event["message"]
            for event in execution_log["payload"]["events"]
        )
        report = live_client.get(f"/report/{repo_id}")
        assert report.status_code == 200
        assert report.json()["verification"] is None


def test_career_guide_style_run_persists_real_pytest_and_ruff_failure(monkeypatch, tmp_path):
    """Three-module repositories without tests reach real TesterAgent commands."""
    init_db()
    for number, filename in enumerate(("app.py", "database.py", "main.py"), start=10):
        (tmp_path / filename).write_text(f"def value():\n    return {number}\n", encoding="utf-8")
    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")
    monkeypatch.setattr(settings, "llm_api_key", "configured-for-test")
    monkeypatch.setattr("devforge.api.execute.create_llm_client", FakeLLM)
    with TestClient(app) as client:
        account = client.post("/auth/register", json={
            "email": "career-guide-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        user_id = account.json()["id"]
        with Session(engine) as session:
            repo = Repository(name="CareerGuide-AI", path=str(tmp_path.resolve()), user_id=user_id)
            session.add(repo)
            session.commit()
            mission = Mission(
                user_id=user_id, repository_id=repo.id, title="Add tests",
                problem="Add tests to the core modules", mission_type="test_coverage",
                affected_files=json.dumps(["app.py", "database.py", "main.py"]),
            )
            session.add(mission)
            session.commit()
            mission_id = mission.id

        start = client.post(f"/execute/{mission_id}")
        assert start.status_code == 202, start.text
        run_id = start.json()["run_id"]
        deadline = time.monotonic() + 30
        state = client.get(f"/execute/{run_id}").json()
        while state["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            state = client.get(f"/execute/{run_id}").json()

        assert state["status"] == "failed"
        assert state["verification"] is not None
        assert state["verification"]["passed"] is False
        assert state["failure"] == {
            "stage": "verification", "category": "no_tests_collected",
            "reason": "pytest collected no tests (exit code 5).",
            "command": "pytest", "exit_code": 5, "created_at": state["failure"]["created_at"],
        }
        assert ("tester", "started") in {
            (event["agent_type"], event["event_type"]) for event in state["events"]
        }
        assert any(event["agent_type"] == "tester" and event["event_type"] == "failed"
                   and "pytest collected no tests" in event["message"] for event in state["events"])
        assert state["artifact"]["status"] == "failed"
        assert client.get(f"/execute/{run_id}/artifact").status_code == 404
        output = state["verification"]["raw_output"]
        assert "$ python -m pytest -q" in output
        assert "$ python -m ruff check ." in output
        assert "$ TODO/FIXME scan" in output
        assert "no tests ran" in output


def test_tester_command_start_failure_is_sanitized_and_persisted(monkeypatch, tmp_path):
    from devforge.verification.runner import VerificationFailure, VerificationRunner

    init_db()
    (tmp_path / "app.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")
    monkeypatch.setattr(settings, "llm_api_key", "configured-for-test")
    monkeypatch.setattr("devforge.api.execute.create_llm_client", FakeLLM)

    async def fail_runner(_self, _repo_path):
        raise VerificationFailure(
            category="command_start_failed", reason="Could not start pytest (PermissionError).",
            command="pytest",
        )

    monkeypatch.setattr(VerificationRunner, "run", fail_runner)
    with TestClient(app) as client:
        account = client.post("/auth/register", json={
            "email": "tester-failure-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        user_id = account.json()["id"]
        with Session(engine) as session:
            repo = Repository(name="tester fixture", path=str(tmp_path.resolve()), user_id=user_id)
            session.add(repo)
            session.commit()
            mission = Mission(
                user_id=user_id, repository_id=repo.id, title="Fix value", problem="Update value",
                mission_type="bug_fix", affected_files=json.dumps(["app.py"]),
            )
            session.add(mission)
            session.commit()
            mission_id = mission.id
        start = client.post(f"/execute/{mission_id}")
        run_id = start.json()["run_id"]
        deadline = time.monotonic() + 30
        state = client.get(f"/execute/{run_id}").json()
        while state["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.1)
            state = client.get(f"/execute/{run_id}").json()

        assert state["status"] == "failed"
        assert state["verification"] is None
        assert state["failure"]["stage"] == "verification"
        assert state["failure"]["category"] == "command_start_failed"
        assert state["failure"]["command"] == "pytest"
        assert state["failure"]["exit_code"] is None
        assert "PermissionError" in state["failure"]["reason"]
        assert "tester" in {event["agent_type"] for event in state["events"]}
        assert "Check: pytest" in next(
            event["message"] for event in state["events"]
            if event["agent_type"] == "orchestrator" and event["event_type"] == "failed"
        )


def test_checkpoint_retry_resumes_workspace_and_verifies_final_delivery(monkeypatch, tmp_path):
    import asyncio

    from devforge.utils.llm import LLMError

    init_db()
    initial_sources = {
        "app.py": "def app_value():\n    return 1\n",
        "database.py": "def db_value():\n    return 1\n",
        "main.py": "def main_value():\n    return 1\n",
    }
    for filename, source in initial_sources.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "from app import app_value\n"
        "from database import db_value\n"
        "from main import main_value\n\n\n"
        "def test_values():\n"
        "    assert app_value() == 2\n"
        "    assert db_value() == 2\n"
        "    assert main_value() == 2\n",
        encoding="utf-8",
    )
    outputs = {
        "app.py": "def app_value():\n    return 2\n",
        "database.py": "def db_value():\n    return 2\n",
        "main.py": "def main_value():\n    return 2\n",
    }
    agent_calls = []

    class CheckpointLLM:
        def __init__(self, attempt):
            self.attempt = attempt

        async def call_text(self, _system_prompt, user_prompt):
            filename = user_prompt.split("Repository relative path: ", 1)[1].splitlines()[0]
            agent_calls.append((self.attempt, filename))
            if self.attempt == 0 and filename == "database.py":
                raise LLMError("fixture provider failure")
            if self.attempt == 1 and filename == "main.py":
                raise LLMError("fixture provider failure")
            if self.attempt == 1:
                await asyncio.sleep(0.25)
            return outputs[filename]

    factories = []

    def make_llm():
        attempt = len(factories)
        factories.append(attempt)
        return CheckpointLLM(attempt)

    monkeypatch.setattr(settings, "auth_secret", "test-secret-for-authentication-0123456789")
    monkeypatch.setattr(settings, "llm_api_key", "configured-for-test")
    monkeypatch.setattr("devforge.api.execute.create_llm_client", make_llm)
    with TestClient(app) as client:
        owner = client.post("/auth/register", json={
            "email": "retry-owner-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        assert owner.status_code == 201
        user_id = owner.json()["id"]
        with Session(engine) as session:
            repo = Repository(name="CareerGuide-AI", path=str(tmp_path.resolve()), user_id=user_id)
            session.add(repo)
            session.commit()
            repo_id = repo.id
            mission = Mission(
                user_id=user_id, repository_id=repo.id, title="Update core modules",
                problem="Update the three core functions", mission_type="bug_fix",
                affected_files=json.dumps(["app.py", "database.py", "main.py"]),
            )
            session.add(mission)
            session.commit()
            mission_id = mission.id

        original_start = client.post(f"/execute/{mission_id}")
        original_id = original_start.json()["run_id"]

        def wait_for_terminal(execution_id):
            deadline = time.monotonic() + 45
            state = client.get(f"/execute/{execution_id}").json()
            while state["status"] == "running" and time.monotonic() < deadline:
                time.sleep(0.1)
                state = client.get(f"/execute/{execution_id}").json()
            assert state["status"] != "running", state
            return state

        original = wait_for_terminal(original_id)
        assert original["status"] == "failed"
        assert [(item["filename"], item["status"]) for item in original["checkpoints"]] == [
            ("app.py", "completed"), ("database.py", "failed"), ("main.py", "not_started"),
        ]
        assert original["artifact"]["status"] == "failed"

        # A different account cannot retry the owner's failed execution.
        other = client.post("/auth/register", json={
            "email": "retry-other-" + str(time.time_ns()) + "@example.test",
            "password": "sufficiently-long-test-password",
        })
        assert other.status_code == 201
        assert client.post(f"/execute/{original_id}/retry").status_code == 404
        client.post("/auth/login", json={
            "email": owner.json()["email"], "password": "sufficiently-long-test-password",
        })

        retry_one_response = client.post(f"/execute/{original_id}/retry")
        assert retry_one_response.status_code == 202, retry_one_response.text
        retry_one_id = retry_one_response.json()["run_id"]
        duplicate = client.post(f"/execute/{original_id}/retry")
        assert duplicate.status_code == 202
        assert duplicate.json()["run_id"] == retry_one_id
        retry_one = wait_for_terminal(retry_one_id)
        assert retry_one["status"] == "failed"
        assert [(item["filename"], item["status"]) for item in retry_one["checkpoints"]] == [
            ("app.py", "completed"), ("database.py", "completed"), ("main.py", "failed"),
        ]
        assert retry_one["artifact"]["status"] == "failed"
        retry_one_stream = client.get(f"/execute/{retry_one_id}/stream").text
        assert '"event_type": "file_skipped"' in retry_one_stream
        assert '"event_type": "file_retry_started"' in retry_one_stream

        retry_two_response = client.post(f"/execute/{retry_one_id}/retry")
        assert retry_two_response.status_code == 202, retry_two_response.text
        retry_two_id = retry_two_response.json()["run_id"]
        retry_two = wait_for_terminal(retry_two_id)
        assert retry_two["status"] == "completed", retry_two
        assert retry_two["verification"]["passed"] is True
        assert retry_two["verification"]["test_count"] == 1
        assert retry_two["artifact"]["status"] == "ready"
        assert retry_two["artifact"]["execution_id"] == retry_two_id
        assert retry_two["artifact"]["execution_id"] != original["artifact"]["execution_id"]
        assert [(item["filename"], item["status"]) for item in retry_two["checkpoints"]] == [
            ("app.py", "completed"), ("database.py", "completed"), ("main.py", "completed"),
        ]
        final_events = client.get(f"/execute/{retry_two_id}/stream").text
        assert '"event_type": "retry_started"' in final_events
        assert '"event_type": "retry_completed"' in final_events
        assert '"agent_type": "tester"' in final_events
        assert "$ python -m pytest -q" in retry_two["verification"]["raw_output"]
        assert client.post(f"/execute/{retry_two_id}/retry").status_code == 409
        report = client.get(f"/report/{repo_id}")
        assert report.status_code == 200
        assert report.json()["execution"]["id"] == retry_two_id
        assert {item["path"] for item in report.json()["changed_files"]} == {
            "app.py", "database.py", "main.py",
        }

        # Only failed/uncompleted files are sent to ImplementerAgent on each retry.
        assert agent_calls == [
            (0, "app.py"), (0, "database.py"),
            (1, "database.py"), (1, "main.py"),
            (2, "main.py"),
        ]
        assert {name: (tmp_path / name).read_text(encoding="utf-8") for name in initial_sources} == initial_sources
        package = client.get(f"/execute/{retry_two_id}/artifact")
        assert package.status_code == 200
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            project_files = {Path(name).name: archive.read(name).decode("utf-8")
                             for name in archive.namelist() if Path(name).name in outputs}
        assert {name: content.replace("\r\n", "\n") for name, content in project_files.items()} == outputs
