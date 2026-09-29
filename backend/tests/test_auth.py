"""Authentication, authorization, and record ownership tests."""
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from devforge.config import ROOT_ENV_FILE, Settings, settings
from devforge.db.models import Evidence, ExecutionRun, Mission, Repository, SubtaskLog, User
from devforge.db.session import engine, init_db
from devforge.main import app

SECRET = "test-auth-secret-with-at-least-32-characters"
PASSWORD = "a-long-test-password-value"


def _register(client: TestClient) -> dict:
    response = client.post("/auth/register", json={
        "email": f"{uuid.uuid4().hex}@example.test", "password": PASSWORD,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_register_login_logout_and_protected_routes(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", SECRET)
    init_db()
    with TestClient(app) as client:
        assert client.get("/auth/me").status_code == 401
        user = _register(client)
        assert "password" not in user and "password_hash" not in user
        assert client.cookies.get("devforge_session")
        assert client.get("/auth/me").json()["id"] == user["id"]
        assert client.get("/repositories").status_code == 200
        with Session(engine) as session:
            stored = session.get(User, user["id"])
            assert stored.password_hash != PASSWORD
            assert stored.password_hash.startswith("pbkdf2_sha256$")

        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/me").status_code == 401
        bad = client.post("/auth/login", json={
            "email": user["email"], "password": "wrong-password-long-enough",
        })
        assert bad.status_code == 401
        good = client.post("/auth/login", json={"email": user["email"], "password": PASSWORD})
        assert good.status_code == 200
        assert client.get("/auth/me").json()["id"] == user["id"]


def test_duplicate_email_returns_conflict(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", SECRET)
    init_db()
    email = f"{uuid.uuid4().hex}@example.test"
    with TestClient(app) as client:
        first = client.post("/auth/register", json={"email": email, "password": PASSWORD})
        assert first.status_code == 201
        duplicate = client.post("/auth/register", json={"email": email, "password": PASSWORD})
        assert duplicate.status_code == 409


def test_missing_auth_secret_returns_service_unavailable_without_creating_user(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "")
    init_db()
    email = f"{uuid.uuid4().hex}@example.test"
    with TestClient(app) as client:
        response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 503
    with Session(engine) as session:
        assert session.exec(select(User).where(User.email == email)).first() is None


def test_auth_secret_alias_and_root_env_path():
    parsed = Settings(_env_file=None, AUTH_SECRET=SECRET)
    assert parsed.auth_secret == SECRET
    assert Settings.model_config["env_file"] == ROOT_ENV_FILE


def test_user_cannot_read_or_change_another_users_records(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", SECRET)
    init_db()
    with TestClient(app) as owner_client:
        owner = _register(owner_client)
        with Session(engine) as session:
            repo = Repository(user_id=owner["id"], name="private", path="/private/repo")
            session.add(repo)
            session.commit()
            session.refresh(repo)
            mission = Mission(
                user_id=owner["id"], repository_id=repo.id, title="Private mission",
                problem="Private problem", mission_type="bug_fix",
            )
            session.add(mission)
            session.commit()
            session.refresh(mission)
            run = ExecutionRun(user_id=owner["id"], mission_id=mission.id)
            session.add(run)
            session.commit()
            session.refresh(run)
            session.add(SubtaskLog(
                user_id=owner["id"], execution_run_id=run.id, agent_type="orchestrator",
                event_type="started", message="private event",
            ))
            session.add(Evidence(
                user_id=owner["id"], execution_id=run.id, repository_id=repo.id,
                evidence_type="MISSION", title="Private evidence", description="Private",
                payload="{}",
            ))
            session.commit()
            repo_id, mission_id, run_id = repo.id, mission.id, run.id

        with TestClient(app) as other_client:
            other = _register(other_client)
            assert other["id"] != owner["id"]
            assert other_client.get("/repositories").json() == []
            assert other_client.get(f"/missions?repository_id={repo_id}").json() == []
            assert other_client.patch(f"/missions/{mission_id}", json={"status": "dismissed"}).status_code == 404
            assert other_client.post(f"/execute/{mission_id}").status_code == 404
            assert other_client.get(f"/execute/{run_id}").status_code == 404
            assert other_client.get(f"/execute/{run_id}/stream").status_code == 404
            assert other_client.post(f"/verify/{run_id}").status_code == 404
            assert other_client.get(f"/report/{repo_id}").status_code == 404
            assert other_client.get(f"/evidence?execution_id={run_id}").json() == []
