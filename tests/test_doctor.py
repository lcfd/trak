from typer.testing import CliRunner

from trak import config
from trak.db.migrations import LATEST_VERSION
from trak.doctor import find_problems
from trak.typer_app import app

runner = CliRunner()


def test_healthy_database(cli_db):
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "Everything is in shape" in result.output
    assert (
        f"Schema version: {LATEST_VERSION} (latest: {LATEST_VERSION})" in result.output
    )
    assert "up to date" in result.output


def test_shows_the_dev_database(cli_db):
    result = runner.invoke(app, ["doctor"], env={config.DEV_ENV_VAR: "1"})

    assert result.exit_code == 0, result.output
    assert "Database (development):" in result.output


def test_stale_schema_is_a_problem(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version = {LATEST_VERSION - 1}")

    stale = LATEST_VERSION - 1
    assert find_problems(engine) == [
        f"The schema is at version {stale}, but trak expects {LATEST_VERSION}."
    ]


def test_dangling_foreign_key_is_a_problem(engine):
    # Outside SQLAlchemy's transactions: SQLite ignores the pragma inside one.
    raw = engine.raw_connection()
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute(
        "INSERT INTO project (id, customer_fk, name, description, rate, archived)"
        " VALUES (1, 999, 'x', '', 0, 0)"
    )
    raw.close()

    assert find_problems(engine) == ["project 1 points to a missing customer."]


def test_healthy_engine_has_no_problems(engine):
    assert find_problems(engine) == []
