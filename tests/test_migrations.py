import pytest
from sqlalchemy import inspect
from sqlmodel import SQLModel

from trak.db import migrations
from trak.db.engine import get_engine
from trak.db.migrations import (
    LATEST_VERSION,
    DatabaseTooNewError,
    get_version,
    migrate,
)


def describe_schema(engine):
    """A comparable description of tables, columns, FKs and indexes."""

    inspector = inspect(engine)
    return {
        table: {
            "columns": {
                c["name"]: (str(c["type"]), c["nullable"], c["primary_key"])
                for c in inspector.get_columns(table)
            },
            "foreign_keys": sorted(
                (tuple(fk["constrained_columns"]), fk["referred_table"])
                for fk in inspector.get_foreign_keys(table)
            ),
            "indexes": sorted(
                (i["name"], tuple(i["column_names"]), bool(i["unique"]))
                for i in inspector.get_indexes(table)
            ),
        }
        for table in inspector.get_table_names()
    }


def test_fresh_database_is_migrated_to_latest(tmp_path):
    engine = get_engine(tmp_path / "db.sqlite3")

    assert get_version(engine) == 0
    assert migrate(engine) == list(range(1, LATEST_VERSION + 1))
    assert get_version(engine) == LATEST_VERSION


def test_migrate_is_idempotent(engine):
    assert migrate(engine) == []
    assert get_version(engine) == LATEST_VERSION


def test_migrations_match_models(tmp_path):
    """If this fails, you changed a model without adding a migration."""

    migrated = get_engine(tmp_path / "migrated.sqlite3")
    migrate(migrated)

    from_models = get_engine(tmp_path / "models.sqlite3")
    SQLModel.metadata.create_all(from_models)

    assert describe_schema(migrated) == describe_schema(from_models)


def test_database_newer_than_trak_is_refused(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version = {LATEST_VERSION + 1}")

    with pytest.raises(DatabaseTooNewError):
        migrate(engine)


def test_failing_migration_is_rolled_back(engine, monkeypatch):
    def broken(conn):
        conn.exec_driver_sql("CREATE TABLE half_done (id INTEGER)")
        raise RuntimeError("boom")

    monkeypatch.setattr(migrations, "MIGRATIONS", [*migrations.MIGRATIONS, broken])
    monkeypatch.setattr(migrations, "LATEST_VERSION", LATEST_VERSION + 1)

    with pytest.raises(RuntimeError):
        migrate(engine)

    assert get_version(engine) == LATEST_VERSION
    assert "half_done" not in inspect(engine).get_table_names()


def test_foreign_keys_are_enforced(engine):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO project (customer_fk, name, description, rate, archived)"
            " VALUES (999, 'x', '', 0, 0)"
        )


def test_0002_names_existing_sessions_with_an_empty_string(tmp_path):
    engine = get_engine(tmp_path / "db.sqlite3")
    with engine.begin() as conn:
        migrations.MIGRATIONS[0](conn)
        conn.exec_driver_sql("PRAGMA user_version = 1")
        conn.exec_driver_sql(
            "INSERT INTO session (start, active) VALUES ('2026-10-14 09:00:00', 0)"
        )

    migrate(engine)

    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM session").scalar_one() == ""
