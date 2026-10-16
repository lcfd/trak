"""`trak status --starship` answered before the app is imported (`trak/starship.py`)."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session as DBSession

from tests.fakes import add
from trak import config, starship
from trak.customers.models import Customer
from trak.db.engine import get_engine
from trak.db.migrations import migrate
from trak.projects.models import Project
from trak.sessions.display import starship_text
from trak.sessions.services import get_active_sessions, start_session


def ago(**delta) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


def test_only_the_starship_arguments(cli_db, monkeypatch):
    monkeypatch.setenv("TRAK_DEV", "0")

    assert starship.run(["status", "-s"]) == ""
    assert starship.run(["status", "--starship"]) == ""
    assert starship.run(["status"]) is None
    assert starship.run(["status", "-s", "--json"]) is None
    assert starship.run(["--json", "status", "-s"]) is None


def test_same_line_as_the_app(cli_db, monkeypatch):
    monkeypatch.setenv("TRAK_DEV", "0")
    acme = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="website", customer_fk=acme.id))
    start_session(cli_db, project_fk=website.id, start=ago(hours=3))
    start_session(cli_db, name="Hero", start=ago(hours=1, minutes=5))
    cli_db.commit()
    line = starship_text(cli_db, get_active_sessions(cli_db))

    assert line == "Hero 1h 5m +1"
    assert starship.run(["status", "-s"]) == line


def test_names_the_session_by_its_project_customer(cli_db, monkeypatch):
    monkeypatch.setenv("TRAK_DEV", "0")
    acme = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="", customer_fk=acme.id))
    start_session(cli_db, project_fk=website.id, start=ago(minutes=30))
    cli_db.commit()

    assert starship.run(["status", "-s"]) == "ACME 0h 30m"


def test_dev_mode_from_settings(cli_db, monkeypatch):
    monkeypatch.delenv("TRAK_DEV", raising=False)
    config.SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SETTINGS_FILE_PATH.write_text("development = true\n")
    engine = get_engine(config.DB_DEV_PATH)
    migrate(engine)
    with DBSession(engine) as dev_db:
        start_session(dev_db, name="Hero")
        dev_db.commit()
    engine.dispose()

    assert starship.run(["status", "-s"]) == "Hero 0h 0m (dev)"


def test_leaves_a_missing_database_to_the_app(monkeypatch):
    monkeypatch.setenv("TRAK_DEV", "0")

    assert not config.DB_PATH.exists()
    assert starship.run(["status", "-s"]) is None
    # Nothing created: the app does it, with its migrations.
    assert not config.DB_PATH.exists()
    assert not config.SETTINGS_FILE_PATH.exists()


def test_leaves_an_unknown_schema_to_the_app(monkeypatch):
    import sqlite3

    monkeypatch.setenv("TRAK_DEV", "0")
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(config.DB_PATH).close()

    assert starship.run(["status", "-s"]) is None
