from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from rich.text import Text
from sqlmodel import Session as DBSession
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter
from tests.fakes import add as add_row
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions import commands
from trak.sessions.display import (
    format_duration,
    format_start,
    started_text,
    stopped_text,
)
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import get_active_sessions, start_session
from trak.typer_app import app

runner = CliRunner()


@pytest.fixture
def invoke(cli_db):
    """Run the CLI, first ending the test's transaction so it doesn't lock the db."""

    def invoke(*args: str):
        cli_db.commit()
        return runner.invoke(app, list(args))

    return invoke


def add_project(db: DBSession, name: str, archived: bool = False) -> Project:
    project = Project(name=name, archived=archived)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def all_sessions(db: DBSession) -> list[Session]:
    db.expire_all()
    return list(db.exec(select(Session).order_by(Session.id)))


# start


def test_start_without_project(cli_db, invoke):
    result = invoke("start")

    assert result.exit_code == 0, result.output
    assert "Session #1" in result.output
    [session] = all_sessions(cli_db)
    assert session.active is True
    assert session.project_fk is None


def test_start_with_project(cli_db, invoke):
    project = add_project(cli_db, "website")

    result = invoke("start", "website")

    assert result.exit_code == 0, result.output
    assert "website" in result.output
    [session] = all_sessions(cli_db)
    assert session.active is True
    assert session.project_fk == project.id


def test_start_with_unknown_project_fails(cli_db, invoke):
    add_project(cli_db, "website")

    result = invoke("start", "nope")

    assert result.exit_code == 1
    assert "This project doesn't exist" in result.output
    assert "website" in result.output
    assert all_sessions(cli_db) == []


def test_start_ignores_archived_projects(cli_db, invoke):
    add_project(cli_db, "old", archived=True)

    result = invoke("start", "old")

    assert result.exit_code == 1
    assert all_sessions(cli_db) == []


def test_start_with_ambiguous_project_fails(cli_db, invoke):
    add_project(cli_db, "website")
    add_project(cli_db, "website")

    result = invoke("start", "website")

    assert result.exit_code == 1
    assert "Ambiguous project" in result.output
    assert all_sessions(cli_db) == []


def test_start_keeps_other_sessions_running(cli_db, invoke):
    invoke("start")
    result = invoke("start")

    assert result.exit_code == 0, result.output
    assert len(get_active_sessions(cli_db)) == 2


# stop


def test_stop_without_active_sessions(cli_db, invoke):
    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "No active sessions" in result.output


def test_stop_the_only_active_session(cli_db, invoke):
    start = datetime.now(UTC) - timedelta(hours=1, minutes=30)
    start_session(cli_db, start=start)

    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "1h 30m" in result.output
    [session] = all_sessions(cli_db)
    assert session.active is False
    assert session.end is not None


def test_stop_with_multiple_active_sessions_asks_to_choose(cli_db, invoke):
    website = add_project(cli_db, "website")
    start_session(cli_db, project_fk=website.id)
    start_session(cli_db)

    result = invoke("stop")

    assert result.exit_code == 1
    assert "Multiple active sessions" in result.output
    assert "website" in result.output
    assert len(get_active_sessions(cli_db)) == 2


def test_stop_by_project(cli_db, invoke):
    website = add_project(cli_db, "website")
    app_project = add_project(cli_db, "app")
    start_session(cli_db, project_fk=website.id)
    still_running = start_session(cli_db, project_fk=app_project.id)

    result = invoke("stop", "website")

    assert result.exit_code == 0, result.output
    cli_db.expire_all()
    assert [s.id for s in get_active_sessions(cli_db)] == [still_running.id]


def test_stop_by_project_without_active_sessions(cli_db, invoke):
    add_project(cli_db, "website")
    start_session(cli_db)

    result = invoke("stop", "website")

    assert result.exit_code == 0, result.output
    assert "No active sessions" in result.output
    assert len(get_active_sessions(cli_db)) == 1


def test_stop_unknown_project_fails(cli_db, invoke):
    start_session(cli_db)

    result = invoke("stop", "nope")

    assert result.exit_code == 1
    assert "This project doesn't exist" in result.output
    assert len(get_active_sessions(cli_db)) == 1


def test_stop_all(cli_db, invoke):
    start_session(cli_db)
    start_session(cli_db)

    result = invoke("stop", "--all")

    assert result.exit_code == 0, result.output
    cli_db.expire_all()
    assert get_active_sessions(cli_db) == []


def test_start_then_stop(cli_db, invoke):
    add_project(cli_db, "website")

    assert invoke("start", "website").exit_code == 0
    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "website" in result.output
    assert "0h 0m" in result.output


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (timedelta(seconds=59), "0h 0m"),
        (timedelta(minutes=90), "1h 30m"),
        (timedelta(days=1, minutes=5), "24h 5m"),
    ],
)
def test_format_duration(duration, expected):
    assert format_duration(duration) == expected


# names and labels


def test_start_with_name(cli_db, invoke):
    customer = add_row(cli_db, Customer(name="ACME"))
    project = add_row(cli_db, Project(name="website", customer_fk=customer.id))

    result = invoke("start", "website", "--name", "Landing page")

    assert result.exit_code == 0, result.output
    assert "Landing page" in result.output
    assert "Project   website" in result.output
    assert "Customer  ACME (from the project)" in result.output
    [session] = all_sessions(cli_db)
    assert session.name == "Landing page"
    assert session.project_fk == project.id


def test_start_shows_only_the_set_fields(cli_db, invoke):
    result = invoke("start")

    assert result.exit_code == 0, result.output
    assert "Started" in result.output
    assert "Project" not in result.output
    assert "Customer" not in result.output
    assert "other session" not in result.output
    assert 'Stop it with "trak stop".' in result.output


def test_start_shows_category_and_own_customer(cli_db, invoke):
    customer = add_row(cli_db, Customer(name="ACME"))
    category = add_row(cli_db, Category(name="Design"))
    tag = add_row(cli_db, Tag(name="urgent"))
    session = start_session(
        cli_db, customer_fk=customer.id, category_fk=category.id, tag_fk=tag.id
    )

    text = Text.from_markup(started_text(cli_db, session)).plain

    assert "Customer  ACME\n" in text
    assert "Category  Design" in text
    assert "Tag       urgent" in text


def test_start_counts_the_other_running_sessions(cli_db, invoke):
    invoke("start")
    invoke("start")
    result = invoke("start")

    assert result.exit_code == 0, result.output
    assert "2 other sessions are running." in result.output


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (datetime(2026, 10, 14, 9, 5), "09:05"),
        (datetime(2026, 10, 12, 9, 5), "Mon 12 Oct 2026 · 09:05"),
    ],
)
def test_format_start(start, expected):
    now = datetime(2026, 10, 14, 18, 0).astimezone()
    assert format_start(start.astimezone(), now=now) == expected


def test_stop_shows_the_name(cli_db, invoke):
    start_session(cli_db, name="Emails")

    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "Emails" in result.output
    assert "Duration" in result.output


def test_label_escapes_markup(cli_db, invoke):
    result = invoke("start", "-n", "[red]oops")

    assert result.exit_code == 0, result.output
    assert "[red]oops" in result.output


def test_stop_shows_the_details(cli_db, invoke):
    customer = add_row(cli_db, Customer(name="ACME"))
    project = add_row(cli_db, Project(name="website", customer_fk=customer.id))
    start = datetime.now(UTC) - timedelta(hours=1, minutes=30)
    start_session(cli_db, name="Landing page", project_fk=project.id, start=start)

    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "Stopped" in result.output
    assert "Landing page" in result.output
    assert "Project   website" in result.output
    assert "Customer  ACME (from the project)" in result.output
    assert "Duration  1h 30m" in result.output
    assert "Total" not in result.output
    assert 'Start a new one with "trak start".' in result.output


def test_stop_counts_the_sessions_still_running(cli_db, invoke):
    website = add_project(cli_db, "website")
    start_session(cli_db, project_fk=website.id)
    start_session(cli_db)
    start_session(cli_db)

    result = invoke("stop", "website")

    assert result.exit_code == 0, result.output
    assert "2 other sessions are still running." in result.output
    assert "trak start" not in result.output


def test_stop_all_shows_the_total(cli_db):
    now = datetime.now(UTC)
    first = start_session(cli_db, name="Emails", start=now - timedelta(hours=1))
    second = start_session(cli_db, name="Calls", start=now - timedelta(minutes=30))
    for session in (first, second):
        session.end = now
        session.active = False

    text = Text.from_markup(stopped_text(cli_db, [first, second])).plain

    assert "Emails" in text
    assert "Calls" in text
    assert "Duration  1h 0m" in text
    assert "Duration  0h 30m" in text
    assert "Total  1h 30m" in text


# interactive start


def test_interactive_start_asks_project_and_customer(
    interactive, monkeypatch, cli_db, invoke
):
    customer = add_row(cli_db, Customer(name="ACME"))
    website = add_row(cli_db, Project(name="website"))
    monkeypatch.setattr(
        commands, "make_prompter", lambda: nullcontext(FakePrompter("website", "ACME"))
    )

    result = invoke("start", "-n", "Landing page")

    assert result.exit_code == 0, result.output
    [session] = all_sessions(cli_db)
    assert session.project_fk == website.id
    assert session.customer_fk == customer.id
    assert session.name == "Landing page"


def test_interactive_start_with_project_does_not_prompt(
    interactive, monkeypatch, cli_db, invoke
):
    add_row(cli_db, Customer(name="ACME"))
    add_project(cli_db, "website")
    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(FakePrompter()))

    result = invoke("start", "website")

    assert result.exit_code == 0, result.output
    [session] = all_sessions(cli_db)
    assert session.customer_fk is None


def test_interactive_start_ctrl_c_starts_nothing(
    interactive, monkeypatch, cli_db, invoke
):
    add_project(cli_db, "website")

    class Interrupted(FakePrompter):
        def ask(self, *args, **kwargs):
            raise SystemExit()

    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(Interrupted()))

    result = invoke("start")

    assert result.exit_code == 130
    assert all_sessions(cli_db) == []


# stop picker


def test_stop_picks_one_of_many(interactive, monkeypatch, cli_db, invoke):
    first = start_session(cli_db, name="Landing page")
    second = start_session(cli_db, name="Emails")
    monkeypatch.setattr(
        commands, "make_prompter", lambda: nullcontext(FakePrompter("Emails"))
    )

    result = invoke("stop")

    assert result.exit_code == 0, result.output
    assert "Emails" in result.output
    assert "Landing page" not in result.output
    cli_db.expire_all()
    assert [s.id for s in get_active_sessions(cli_db)] == [first.id]
    assert second.id not in [s.id for s in get_active_sessions(cli_db)]


def test_stop_all_skips_the_picker(interactive, monkeypatch, cli_db, invoke):
    start_session(cli_db)
    start_session(cli_db)
    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(FakePrompter()))

    result = invoke("stop", "--all")

    assert result.exit_code == 0, result.output
    cli_db.expire_all()
    assert get_active_sessions(cli_db) == []


# going back (Esc or q)


def test_going_back_from_start_starts_nothing(interactive, monkeypatch, cli_db, invoke):
    add_project(cli_db, "website")
    monkeypatch.setattr(
        commands, "make_prompter", lambda: nullcontext(FakePrompter(PromptCancelled()))
    )

    result = invoke("start")

    assert result.exit_code == 1
    assert "No session was started" in result.output
    assert all_sessions(cli_db) == []


def test_going_back_from_stop_stops_nothing(interactive, monkeypatch, cli_db, invoke):
    start_session(cli_db)
    start_session(cli_db)
    monkeypatch.setattr(
        commands, "make_prompter", lambda: nullcontext(FakePrompter(PromptCancelled()))
    )

    result = invoke("stop")

    assert result.exit_code == 1
    assert "No session was stopped" in result.output
    cli_db.expire_all()
    assert len(get_active_sessions(cli_db)) == 2
