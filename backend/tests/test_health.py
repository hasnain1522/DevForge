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
        # Local-path repositories have no canonical remote source URL.
        assert result.source_url is None
        # Clean up
        session.delete(result)
        session.commit()


def test_product_data_apis_require_authentication():
    """Owned repository and execution APIs reject anonymous access."""
    assert client.post("/execute/fake-mission-id").status_code == 401
    assert client.post("/verify/fake-run-id").status_code == 401
    assert client.get("/report/fake-repo-id").status_code == 401
    assert client.get("/evidence").status_code == 401
    assert client.get("/repositories").status_code == 401
