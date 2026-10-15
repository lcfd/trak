"""`trak dev fill`: years of made-up data in the dev database."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import select
from typer.testing import CliRunner

from trak import config
from trak.customers.models import Customer
from trak.db.engine import get_engine
from trak.db.migrations import migrate
from trak.dev.fill import clear, fill, has_data
from trak.doctor import find_problems
from trak.goals.models import Goal
from trak.goals.services import upcoming_goals
from trak.labels.links import tag_names
from trak.projects.models import Project
from trak.sessions.models import Session
from trak.typer_app import app

runner = CliRunner()

TODAY = date(2026, 10, 15)
NOW = datetime.combine(TODAY, datetime.min.time()).astimezone() + timedelta(hours=15)


@pytest.fixture
def filled(engine, db):
    fill(db, today=TODAY, now=NOW.astimezone(UTC), years=3, seed=1)
    return db


def aware(moment: datetime) -> datetime:
    # SQLite gives naive datetimes back: they're UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def test_spans_the_years_up_to_today(filled):
    starts = [aware(s.start) for s in filled.exec(select(Session))]

    assert min(starts).date() <= TODAY - timedelta(days=365 * 3 - 7)
    assert max(starts) <= NOW
    # Heavy use: thousands of sessions.
    assert len(starts) > 2000


def test_sessions_are_consistent(filled):
    sessions = list(filled.exec(select(Session)))
    projects = {p.id: p for p in filled.exec(select(Project))}

    running = [s for s in sessions if s.active]
    assert len(running) == 2
    assert all(s.end is None for s in running)
    for session in sessions:
        if not session.active:
            assert session.end is not None
            assert aware(session.start) < aware(session.end) <= NOW
        # A session on a project with a customer takes the customer from it.
        project = projects.get(session.project_fk)
        if project and project.customer_fk:
            assert session.customer_fk is None
    assert any(s.project_fk is None for s in sessions)
    assert any(s.project_fk is None and s.customer_fk for s in sessions)


def test_projects_cover_past_present_and_future(filled):
    projects = list(filled.exec(select(Project)))

    assert any(p.archived for p in projects)
    assert any(p.customer_fk is None for p in projects)
    assert any(p.start and p.start > TODAY for p in projects)
    assert any(p.end is None for p in projects)
    for project in projects:
        if project.start and project.end:
            assert project.start <= project.end
    names = [p.name for p in projects]
    assert len(names) == len(set(names))


def test_sessions_projects_and_customers_have_labels(filled):
    db = filled
    sessions = db.exec(select(Session)).all()
    tags = [len(tag_names(db, s)) for s in sessions[:500]]
    assert all(s.category_fk is not None for s in sessions)
    assert max(tags) >= 2 and min(tags) == 0
    for model in (Project, Customer):
        rows = db.exec(select(model)).all()
        assert any(row.category_fk for row in rows)
        assert any(tag_names(db, row) for row in rows)


def test_goals_past_and_upcoming(filled):
    goals = list(filled.exec(select(Goal)))

    assert all(g.start <= g.deadline and g.hours > 0 for g in goals)
    assert any(g.deadline < TODAY for g in goals)
    assert upcoming_goals(filled, on=TODAY)


def test_the_database_stays_healthy(engine, filled):
    assert find_problems(engine) == []


def test_same_seed_same_data(tmp_path):
    def names(path):
        engine = get_engine(path)
        migrate(engine)
        with DBSession(engine) as db:
            fill(db, today=TODAY, now=NOW, years=1, seed=7)
            result = [(s.name, s.start) for s in db.exec(select(Session))]
        engine.dispose()
        return result

    assert names(tmp_path / "a.sqlite3") == names(tmp_path / "b.sqlite3")


def test_clear_empties_the_database(filled):
    clear(filled)

    assert not has_data(filled)


# The command


def dev_db() -> DBSession:
    return DBSession(get_engine(config.DB_DEV_PATH))


def test_fill_writes_the_dev_database(cli_db):
    result = runner.invoke(app, ["dev", "fill", "--years", "1", "--seed", "3"])

    assert result.exit_code == 0, result.output
    assert "Dev database filled" in result.output
    with dev_db() as db:
        assert db.exec(select(Session)).first() is not None
    # The real database stays untouched.
    assert not has_data(cli_db)


def test_fill_refuses_a_database_with_data():
    runner.invoke(app, ["dev", "fill", "--years", "1"])

    result = runner.invoke(app, ["dev", "fill", "--years", "1"])

    assert result.exit_code == 1
    assert "--reset" in result.output


def test_reset_replaces_the_data():
    runner.invoke(app, ["dev", "fill", "--years", "1"])
    with dev_db() as db:
        db.add(Customer(name="Leftover"))
        db.commit()

    result = runner.invoke(app, ["dev", "fill", "--years", "1", "--reset"])

    assert result.exit_code == 0, result.output
    with dev_db() as db:
        names = [c.name for c in db.exec(select(Customer))]
    assert "Leftover" not in names


def test_dev_is_in_the_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "dev" in result.output


# trak dev toggle


def settings() -> str:
    return config.SETTINGS_FILE_PATH.read_text()


def test_toggle_needs_yes_without_a_terminal():
    result = runner.invoke(app, ["dev", "toggle"])

    assert result.exit_code == 1
    assert "--yes" in result.output
    assert "development" not in settings()


def test_toggle_flips_the_setting_and_keeps_the_rest():
    config.SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SETTINGS_FILE_PATH.write_text(
        'currency = "€"\nTRAK_DEV=true\n\n[report]\ndevelopment = 1\n'
    )

    off = runner.invoke(app, ["dev", "toggle", "--yes"])
    assert off.exit_code == 0, off.output
    assert "Dev mode is off" in off.output
    assert (
        settings()
        == 'currency = "€"\ndevelopment = false\n\n[report]\ndevelopment = 1\n'
    )

    on = runner.invoke(app, ["dev", "toggle", "-y"])
    assert "Dev mode is on" in on.output
    assert "development = true" in settings()


def test_toggle_on_when_already_on_changes_nothing():
    result = runner.invoke(app, ["dev", "toggle", "--off"])

    assert result.exit_code == 0, result.output
    assert "already off" in result.output
    assert "development" not in settings()


def test_toggle_asks_in_a_terminal(interactive, answers):
    answers(confirm=False)
    kept = runner.invoke(app, ["dev", "toggle"])
    answers(confirm=True)
    toggled = runner.invoke(app, ["dev", "toggle"])

    assert kept.exit_code == 1 and "Dev mode didn't change" in kept.output
    assert toggled.exit_code == 0, toggled.output
    assert settings() == "development = true\n"


def test_toggle_json():
    result = runner.invoke(app, ["--json", "dev", "toggle", "--on", "--yes"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "development": True,
        "settings": str(config.SETTINGS_FILE_PATH),
        "database": str(config.DB_DEV_PATH),
    }


def test_toggle_warns_that_the_env_var_wins(monkeypatch):
    monkeypatch.setenv(config.DEV_ENV_VAR, "1")

    result = runner.invoke(app, ["dev", "toggle", "--on", "--yes"])

    assert result.exit_code == 0, result.output
    assert "Dev mode is on" in result.output
    assert f"{config.DEV_ENV_VAR}=1 wins" in result.output
