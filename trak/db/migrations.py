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
            start DATE,
            "end" DATE,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_fk) REFERENCES customer (id)
        )
    """)
    conn.exec_driver_sql("""
        CREATE TABLE session (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
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


def _0002_categories_and_tags(conn: Connection) -> None:
    """
    Projects and Customers get a Category; Sessions, Projects and Customers
    get any number of Tags, in link tables. A Session's single `tag_fk`
    moves to `session_tag`, and the column goes.
    """

    for table in ("project", "customer"):
        conn.exec_driver_sql(
            f"ALTER TABLE {table} ADD COLUMN category_fk INTEGER "
            "REFERENCES category (id)"
        )

    # Rebuild session without tag_fk: nothing references it yet.
    conn.exec_driver_sql("DROP INDEX ix_session_active")
    conn.exec_driver_sql("ALTER TABLE session RENAME TO session_old")
    conn.exec_driver_sql("""
        CREATE TABLE session (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            customer_fk INTEGER,
            project_fk INTEGER,
            category_fk INTEGER,
            start DATETIME NOT NULL,
            "end" DATETIME,
            active BOOLEAN NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (customer_fk) REFERENCES customer (id),
            FOREIGN KEY (project_fk) REFERENCES project (id),
            FOREIGN KEY (category_fk) REFERENCES category (id)
        )
    """)
    conn.exec_driver_sql("""
        INSERT INTO session
            (id, name, customer_fk, project_fk, category_fk, start, "end", active)
        SELECT id, name, customer_fk, project_fk, category_fk, start, "end", active
        FROM session_old
    """)
    conn.exec_driver_sql("CREATE INDEX ix_session_active ON session (active)")

    for owner in ("session", "project", "customer"):
        conn.exec_driver_sql(f"""
            CREATE TABLE {owner}_tag (
                {owner}_fk INTEGER NOT NULL,
                tag_fk INTEGER NOT NULL,
                PRIMARY KEY ({owner}_fk, tag_fk),
                FOREIGN KEY ({owner}_fk) REFERENCES {owner} (id),
                FOREIGN KEY (tag_fk) REFERENCES tag (id)
            )
        """)
    conn.exec_driver_sql("""
        INSERT INTO session_tag (session_fk, tag_fk)
        SELECT id, tag_fk FROM session_old WHERE tag_fk IS NOT NULL
    """)
    conn.exec_driver_sql("DROP TABLE session_old")


MIGRATIONS: list[Callable[[Connection], None]] = [
    _0001_initial,
    _0002_categories_and_tags,
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
