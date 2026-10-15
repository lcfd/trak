"""
Database migrations, without Alembic.

The schema version is stored in SQLite's built-in `PRAGMA user_version`
(an integer in the database header, 0 on a fresh database).

`MIGRATIONS` is an append-only list: migration N (1-based) brings the
database from version N-1 to version N. On startup `migrate` runs every
pending migration, each one in its own transaction together with the
version bump, so a failing migration leaves the database untouched.

Rules:
- Never edit or reorder a migration that has been released: add a new one.
- Write migrations as plain SQL, never with `SQLModel.metadata.create_all`,
  because the models will change while old migrations must not.
- When you change a model, add a migration. `tests/test_migrations.py`
  fails if the migrated schema and the models diverge.
- SQLite has limited `ALTER TABLE`: to change a column, create the new
  table, copy the data, drop the old table and rename the new one.
"""

from collections.abc import Callable

from sqlalchemy import Connection, Engine


class DatabaseTooNewError(Exception):
    """The database was migrated by a newer version of trak."""


def _0001_initial(conn: Connection) -> None:
    conn.exec_driver_sql("""
        CREATE TABLE customer (
            id INTEGER NOT NULL,
            name VARCHAR,
            PRIMARY KEY (id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE category (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE tag (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE project (
            id INTEGER NOT NULL,
            customer_fk INTEGER,
            name VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            rate INTEGER NOT NULL,
            archived BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_fk) REFERENCES customer (id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE session (
            id INTEGER NOT NULL,
            customer_fk INTEGER,
            project_fk INTEGER,
            category_fk INTEGER,
            tag_fk INTEGER,
            start DATETIME NOT NULL,
            "end" DATETIME,
            active BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_fk) REFERENCES customer (id),
            FOREIGN KEY (project_fk) REFERENCES project (id),
            FOREIGN KEY (category_fk) REFERENCES category (id),
            FOREIGN KEY (tag_fk) REFERENCES tag (id)
        )
    """)
    conn.exec_driver_sql("CREATE INDEX ix_session_active ON session (active)")


def _0002_session_name(conn: Connection) -> None:
    conn.exec_driver_sql(
        "ALTER TABLE session ADD COLUMN name VARCHAR NOT NULL DEFAULT ''"
    )


def _0003_goal(conn: Connection) -> None:
    conn.exec_driver_sql("""
        CREATE TABLE goal (
            id INTEGER NOT NULL,
            project_fk INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            hours INTEGER NOT NULL,
            start DATE NOT NULL,
            deadline DATE NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (project_fk) REFERENCES project (id)
        )
    """)


def _0004_project_dates(conn: Connection) -> None:
    conn.exec_driver_sql("ALTER TABLE project ADD COLUMN start DATE")
    conn.exec_driver_sql('ALTER TABLE project ADD COLUMN "end" DATE')


MIGRATIONS: list[Callable[[Connection], None]] = [
    _0001_initial,
    _0002_session_name,
    _0003_goal,
    _0004_project_dates,
]

LATEST_VERSION = len(MIGRATIONS)


def get_version(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.exec_driver_sql("PRAGMA user_version").scalar_one()


def migrate(engine: Engine) -> list[int]:
    """Apply the pending migrations. Return the versions that were applied."""

    current = get_version(engine)

    if current > LATEST_VERSION:
        raise DatabaseTooNewError(
            f"The database is at version {current}, "
            f"but this version of trak only knows up to {LATEST_VERSION}."
        )

    applied = []
    for version in range(current + 1, LATEST_VERSION + 1):
        with engine.begin() as conn:
            MIGRATIONS[version - 1](conn)
            conn.exec_driver_sql(f"PRAGMA user_version = {version}")
        applied.append(version)

    return applied
