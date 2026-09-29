"""Repository naming and stable source identity tests."""
import time

from sqlmodel import Session

from devforge.api.analyze import _get_or_create_repository
from devforge.db.models import Repository, User
from devforge.db.session import engine, init_db


def test_reanalyzing_github_url_keeps_repository_id_and_updates_display_name(tmp_path):
    init_db()
    first_clone = tmp_path / "first" / "repository"
    second_clone = tmp_path / "second" / "repository"
    first_clone.mkdir(parents=True)
    second_clone.mkdir(parents=True)
    (first_clone / ".git").mkdir()
    (first_clone / ".git" / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/hasnain1522/CareerGuide-AI.git\n',
        encoding="utf-8",
    )
    with Session(engine) as session:
        user = User(email=f"repo-name-{time.time_ns()}@example.test", password_hash="test")
        session.add(user)
        session.commit()
        session.refresh(user)

        legacy = Repository(
            user_id=user.id, name="repository", path=str(first_clone), source_url=None,
        )
        session.add(legacy)
        session.commit()
        first_id = legacy.id
        second = _get_or_create_repository(
            session, user.id, "https://github.com/hasnain1522/CareerGuide-AI.git", second_clone,
        )

        assert second.id == first_id
        assert second.name == "CareerGuide-AI"
        assert second.path == str(second_clone)
        assert second.source_url == "https://github.com/hasnain1522/careerguide-ai.git"
