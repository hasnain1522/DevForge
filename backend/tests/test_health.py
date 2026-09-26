"""Phase 1 smoke tests — health endpoint and database initialisation."""
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from devforge.db.models import Repository
from devforge.db.session import engine, init_db
from devforge.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data


def test_db_tables_created():
    """Verify that init_db creates all expected tables."""
    init_db()
    # Simple write-read round-trip to confirm Repository table exists
    with Session(engine) as session:
        repo = Repository(name="test-repo", path="/tmp/test")
        session.add(repo)
        session.commit()
        session.refresh(repo)

        result = session.exec(select(Repository).where(Repository.id == repo.id)).first()
        assert result is not None
        assert result.name == "test-repo"
        assert result.status == "pending"
        # Confirm no source_url column exists on the model
        assert not hasattr(result, "source_url")
        # Clean up
        session.delete(result)
        session.commit()


def test_phase3_stub_routes_return_not_implemented():
    """Phase 3+ routes should still return a not-implemented response, not 500."""
    routes_to_check = [
        ("/execute/fake-mission-id", "POST"),
        ("/verify/fake-run-id", "POST"),
        ("/report/fake-repo-id", "GET"),
    ]
    for path, method in routes_to_check:
        if method == "POST":
            resp = client.post(path)
        else:
            resp = client.get(path)
        assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}"
        assert "detail" in resp.json()
