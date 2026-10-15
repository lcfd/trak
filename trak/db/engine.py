from pathlib import Path

from sqlalchemy import Engine, event
from sqlmodel import create_engine

# Import every table model, so they are all registered in SQLModel.metadata.
from trak.customers.models import Customer  # noqa: F401
from trak.goals.models import Goal  # noqa: F401
from trak.projects.models import Project  # noqa: F401
from trak.sessions.models import Category, Session, Tag  # noqa: F401


def get_engine(db_path: Path, echo: bool = False) -> Engine:
    """Create the SQLite engine, creating the parent folder if needed."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=echo)

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_connection, _connection_record):
        # Let SQLAlchemy drive transactions, so that DDL in migrations
        # is transactional too (pysqlite doesn't BEGIN before DDL).
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    @event.listens_for(engine, "begin")
    def on_begin(connection):
        connection.exec_driver_sql("BEGIN")

    return engine
