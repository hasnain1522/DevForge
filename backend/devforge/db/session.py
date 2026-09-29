"""Database session factory and table initialisation."""
from sqlmodel import Session, SQLModel, create_engine

from devforge.config import settings


def _database_url() -> str:
    """Return a SQLAlchemy-compatible database URL for SQLite or PostgreSQL."""
    url = settings.database_url.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=settings.debug,
)


def init_db() -> None:
    """Create tables and run SQLite-only legacy migrations."""
    from devforge.db import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        _migrate_sqlite_ownership()


def _migrate_sqlite_ownership() -> None:
    """Add nullable ownership columns for legacy rows; never claim them for a user."""
    ownership_tables = {
        "repositories": None,
        "repository_snapshots": ("repository_id", "repositories"),
        "missions": ("repository_id", "repositories"),
        "execution_runs": ("mission_id", "missions"),
        "subtask_logs": ("execution_run_id", "execution_runs"),
        "verification_results": ("execution_run_id", "execution_runs"),
        "impact_reports": ("mission_id", "missions"),
    }
    with engine.begin() as connection:
        execution_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(execution_runs)")
        }
        if "parent_execution_run_id" not in execution_columns:
            connection.exec_driver_sql(
                "ALTER TABLE execution_runs ADD COLUMN parent_execution_run_id VARCHAR "
                "REFERENCES execution_runs(id)"
            )
        if "workspace_path" not in execution_columns:
            connection.exec_driver_sql("ALTER TABLE execution_runs ADD COLUMN workspace_path VARCHAR")
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_runs_parent_execution_run_id "
            "ON execution_runs(parent_execution_run_id)"
        )
        repository_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(repositories)")
        }
        if "source_url" not in repository_columns:
            connection.exec_driver_sql("ALTER TABLE repositories ADD COLUMN source_url VARCHAR")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_repositories_source_url ON repositories(source_url)"
        )
        for table, parent in ownership_tables.items():
            columns = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR REFERENCES users(id)"
                )
            if parent:
                parent_key, parent_table = parent
                connection.exec_driver_sql(
                    f"UPDATE {table} SET user_id = (SELECT user_id FROM {parent_table} "
                    f"WHERE {parent_table}.id = {table}.{parent_key}) "
                    f"WHERE user_id IS NULL"
                )
            connection.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table}(user_id)"
            )


def get_session():
    """FastAPI dependency: yields a database session."""
    with Session(engine) as session:
        yield session
