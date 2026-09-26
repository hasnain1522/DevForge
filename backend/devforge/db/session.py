"""Database session factory and table initialisation."""
from sqlmodel import Session, SQLModel, create_engine

from devforge.config import settings

# SQLite engine — connect_args only needed for SQLite
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)


def init_db() -> None:
    """Create all tables if they do not exist."""
    # Import models so SQLModel registers them before create_all
    from devforge.db import models  # noqa: F401
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a database session."""
    with Session(engine) as session:
        yield session
