from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions.creating import (
    ask_new_session,
    parse_duration,
    parse_end,
    parse_past_start,
)
from trak.sessions.models import Session
from trak.sessions.services import create_session
from trak.typer_app import app

runner = CliRunner()

NOW = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, ["sessions", "create", *args])


def local(moment: datetime) -> str:
    return f"{moment.astimezone():%Y-%m-%d %H:%M}"


def yesterday_at_9() -> datetime:
    day = datetime.now().astimezone() - timedelta(days=1)
    return day.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(UTC)


def sessions(db) -> list[Session]:
    db.expire_all()
    return list(db.exec(select(Session)))


# services


def test_create_session_is_stopped(db):
    session = create_session(
        db, start=NOW - timedelta(hours=2), end=NOW, now=NOW, name=" Fix "
    )

    assert (session.active, session.name) == (False, "Fix")
    assert session.end - session.start == timedelta(hours=2)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (NOW, NOW - timedelta(minutes=1), "end before it starts"),
        (NOW, NOW + timedelta(minutes=1), "end in the future"),
    ],
)
def test_create_session_rejects_invalid_times(db, start, end, message):
    with pytest.raises(ValueError, match=message):
        create_session(db, start=start, end=end, now=NOW)


# parsing


@pytest.mark.parametrize(
    ("text", "duration"),
    [
        ("1h30m", timedelta(hours=1, minutes=30)),
        ("2h", timedelta(hours=2)),
        ("45m", timedelta(minutes=45)),
        ("1H 5M", timedelta(hours=1, minutes=5)),
        ("10:30", None),
        ("", None),
        ("h", None),
    ],
)
def test_parse_duration(text, duration):
    assert parse_duration(text) == duration


def test_parse_past_start_needs_a_value():
    with pytest.raises(ValueError, match="needs a start"):
        parse_past_start("  ", now=NOW)


def test_parse_end_takes_a_time_or_a_duration():
    start = NOW - timedelta(hours=3)

    assert parse_end("2h", start, now=NOW) == start + timedelta(hours=2)
    assert parse_end(local(NOW - timedelta(hours=1)), start, now=NOW) == (
        NOW - timedelta(hours=1)
    )
    assert parse_end("", start, now=NOW) == NOW


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("4h", "end in the future"),
        ("0m", "at least a minute"),
        ("bad", "HH:MM"),
    ],
)
def test_parse_end_rejects(text, message):
    with pytest.raises(ValueError, match=message):
        parse_end(text, NOW - timedelta(hours=3), now=NOW)


# guided


def test_ask_new_session(db):
    project = add(db, Project(name="website"))
    start = yesterday_at_9()

    fields = ask_new_session(
        db, FakePrompter("Backfill", "website", local(start), "1h30m")
    )

    assert fields == {
        "name": "Backfill",
        "project_fk": project.id,
        "customer_fk": None,
        "category_fk": None,
        "tag_fk": None,
        "start": start,
        "end": start + timedelta(hours=1, minutes=30),
    }


def test_ask_new_session_can_be_declined(db):
    prompter = FakePrompter("", local(yesterday_at_9()), "1h", confirm=False)

    assert ask_new_session(db, prompter) is None


# the command


def test_create_with_options(cli_db):
    add(cli_db, Project(name="website"))
    acme = add(cli_db, Customer(name="ACME"))
    start = yesterday_at_9()

    result = invoke(
        cli_db,
        "website",
        "--start",
        local(start),
        "--end",
        "2h15m",
        "--name",
        "Backfill",
        "--customer",
        "ACME",
    )

    assert result.exit_code == 0, result.output
    assert "Duration  2h 15m" in result.output
    [session] = sessions(cli_db)
    assert (session.name, session.customer_fk, session.active) == (
        "Backfill",
        acme.id,
        False,
    )
    assert session.end - session.start == timedelta(hours=2, minutes=15)


def test_create_with_an_end_time(cli_db):
    start = yesterday_at_9()

    result = invoke(
        cli_db,
        "-s",
        local(start),
        "-e",
        local(start + timedelta(hours=1)),
    )

    assert result.exit_code == 0, result.output
    [session] = sessions(cli_db)
    assert session.end == start + timedelta(hours=1)


def test_create_needs_a_start_with_a_project(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "website")

    assert result.exit_code == 1
    assert "--start" in result.output
    assert sessions(cli_db) == []


def test_create_rejects_an_end_before_the_start(cli_db):
    start = yesterday_at_9()

    result = invoke(
        cli_db,
        "-s",
        local(start),
        "-e",
        local(start - timedelta(hours=1)),
    )

    assert result.exit_code == 1
    assert "end before it starts" in result.output


def test_create_of_an_unknown_project(cli_db):
    result = invoke(cli_db, "nope", "-s", "09:00")

    assert result.exit_code == 1
    assert "doesn't exist" in result.output


def test_create_without_options_needs_a_terminal(cli_db):
    result = invoke(cli_db)

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


def test_create_asks_every_field(cli_db, interactive, answers):
    start = yesterday_at_9()
    answers("Backfill", local(start), "45m")

    result = invoke(cli_db)

    assert result.exit_code == 0, result.output
    [session] = sessions(cli_db)
    assert session.name == "Backfill"
    assert session.end - session.start == timedelta(minutes=45)


def test_create_cancelled(cli_db, interactive, answers):
    answers(PromptCancelled())

    result = invoke(cli_db)

    assert result.exit_code == 1
    assert "No session was created" in result.output
    assert sessions(cli_db) == []
