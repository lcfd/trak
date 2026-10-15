from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.guided import (
    SessionFields,
    ask_session_fields,
    ask_session_to_stop,
    parse_start,
    pick_many,
)
from trak.sessions.models import Category, Tag
from trak.sessions.services import start_session
from trak.typer_app import app

runner = CliRunner()


# parse_start

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", ["", "  ", "now", "NOW"])
def test_parse_start_empty_means_now(value):
    assert parse_start(value, now=NOW) is None


def test_parse_start_time_is_today_in_local_time():
    parsed = parse_start("09:30", now=NOW)
    local = parsed.astimezone()

    assert parsed.tzinfo == UTC
    assert (local.hour, local.minute) == (9, 30)
    assert local.date() == NOW.astimezone().date()


def test_parse_start_full_datetime():
    parsed = parse_start("2026-10-13 18:45", now=NOW)

    assert parsed.astimezone().replace(tzinfo=None) == datetime(2026, 10, 13, 18, 45)


@pytest.mark.parametrize("value", ["25:99", "yesterday", "2026-13-01 10:00"])
def test_parse_start_rejects_garbage(value):
    with pytest.raises(ValueError, match="HH:MM"):
        parse_start(value, now=NOW)


def test_parse_start_rejects_the_future():
    with pytest.raises(ValueError, match="future"):
        parse_start(
            (NOW + timedelta(days=1)).astimezone().strftime("%Y-%m-%d %H:%M"), now=NOW
        )


# ask_session_fields


def test_empty_database_only_asks_the_start(db):
    prompter = FakePrompter("", "")

    fields = ask_session_fields(db, prompter)

    assert prompter.asked == ["Name", "Start"]
    assert fields == SessionFields()


def test_asks_every_field(db):
    customer = add(db, Customer(name="ACME"))
    project = add(db, Project(name="website"))
    category = add(db, Category(name="dev"))
    tag = add(db, Tag(name="urgent"))
    add(db, Tag(name="billable"))
    prompter = FakePrompter(
        "Landing page", "website", "ACME", "dev", "urgent", "Done", "2026-10-13 09:00"
    )

    fields = ask_session_fields(db, prompter)

    tags = "Tags · Enter toggles"
    assert prompter.asked == [
        "Name",
        "Project",
        "Customer",
        "Category",
        tags,
        tags,
        "Start",
    ]
    assert prompter.notes == {"Tags": "urgent"}
    assert fields.name == "Landing page"
    assert fields.project_fk == project.id
    assert fields.customer_fk == customer.id
    assert fields.category_fk == category.id
    assert fields.tag_fks == [tag.id]
    assert fields.start == parse_start("2026-10-13 09:00")


def test_every_field_can_be_none(db):
    add(db, Customer(name="ACME"))
    add(db, Project(name="website"))
    prompter = FakePrompter("", "None", "None", "")

    assert ask_session_fields(db, prompter) == SessionFields()


def test_skips_customer_when_the_project_has_one(db):
    customer = add(db, Customer(name="ACME"))
    add(db, Project(name="website", customer_fk=customer.id))
    prompter = FakePrompter("", "website", "")

    fields = ask_session_fields(db, prompter)

    assert "Customer" not in prompter.asked
    assert fields.customer_fk is None


def test_project_argument_is_the_default(db):
    add(db, Project(name="app"))
    website = add(db, Project(name="website"))
    prompter = FakePrompter("", "website", "")

    ask_session_fields(db, prompter, project=website)

    assert prompter.defaults["Project"] == website.id


def test_archived_projects_are_not_offered(db):
    add(db, Project(name="old", archived=True))
    prompter = FakePrompter("", "")

    ask_session_fields(db, prompter)

    assert "Project" not in prompter.asked


def test_declining_the_confirmation_returns_none(db):
    assert ask_session_fields(db, FakePrompter("", "", confirm=False)) is None


# trak start -g


def fake_guided(monkeypatch, result):
    def fake(db, prompter, **kwargs):
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(commands, "ask_session_fields", fake)


def test_guided_needs_a_terminal():
    result = runner.invoke(app, ["start", "-g"])

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


def test_guided_starts_the_session(interactive, monkeypatch, cli_db):
    category = add(cli_db, Category(name="dev"))
    start = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    fake_guided(monkeypatch, SessionFields(category_fk=category.id, start=start))
    cli_db.commit()

    result = runner.invoke(app, ["start", "--guided"])

    assert result.exit_code == 0, result.output
    [session] = commands.get_active_sessions(cli_db)
    assert session.category_fk == category.id
    assert session.start == start


def test_guided_cancelled(interactive, monkeypatch, cli_db):
    fake_guided(monkeypatch, None)

    result = runner.invoke(app, ["start", "-g"])

    assert result.exit_code == 1
    assert "No session was started" in result.output
    assert commands.get_active_sessions(cli_db) == []


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit()])
def test_guided_interrupted(interactive, monkeypatch, cli_db, error):
    fake_guided(monkeypatch, error)

    result = runner.invoke(app, ["start", "-g"])

    assert result.exit_code == 130
    assert commands.get_active_sessions(cli_db) == []


def test_guided_with_unknown_project_fails_before_prompting(
    interactive, monkeypatch, cli_db
):
    fake_guided(monkeypatch, AssertionError("should not prompt"))

    result = runner.invoke(app, ["start", "nope", "-g"])

    assert result.exit_code == 1
    assert "This project doesn't exist" in result.output


# name


def test_guided_name_defaults_to_the_name_option(db):
    fields = ask_session_fields(db, FakePrompter("", ""), name="Landing page")

    assert fields.name == "Landing page"


def test_guided_name_is_stripped(db):
    fields = ask_session_fields(db, FakePrompter("  Landing page  ", ""))

    assert fields.name == "Landing page"


def test_guided_passes_the_name_option(interactive, monkeypatch, cli_db):
    seen = {}

    def fake(db, prompter, **kwargs):
        seen.update(kwargs)
        return SessionFields(name=kwargs["name"])

    monkeypatch.setattr(commands, "ask_session_fields", fake)

    result = runner.invoke(app, ["start", "-g", "--name", "Landing page"])

    assert result.exit_code == 0, result.output
    assert seen["name"] == "Landing page"
    [session] = commands.get_active_sessions(cli_db)
    assert session.name == "Landing page"


# pick_many


def test_pick_many_toggles_until_done(db):
    rows = [add(db, Tag(name=name)) for name in ("a", "b", "c")]
    prompter = FakePrompter("b", "c", "b ✓", "Done")

    picked = pick_many(prompter, "Tags", rows, selected=[rows[0].id])

    assert picked == [rows[0].id, rows[2].id]
    assert prompter.notes == {"Tags": "a, c"}
    # The cursor stays on the last row toggled.
    assert prompter.defaults["Tags · Enter toggles"] == rows[1].id


def test_pick_many_starts_on_done(db):
    prompter = FakePrompter("Done")

    assert pick_many(prompter, "Tags", [add(db, Tag(name="a"))], selected=[]) == []
    assert prompter.notes == {"Tags": "—"}


# ask_session_to_stop


def test_ask_session_to_stop_offers_every_session(db):
    website = add(db, Project(name="website"))
    first = start_session(db, name="Landing page", project_fk=website.id)
    second = start_session(db, name="Emails")
    prompter = FakePrompter("Emails")
    options = []
    prompter.ask = lambda label, opts, **kw: (
        options.extend(opts),
        FakePrompter.ask(prompter, label, opts, **kw),
    )[1]

    picked = ask_session_to_stop(db, prompter, [first, second])

    assert picked == second
    assert options[0]["name"].startswith("Landing page · website  (since ")
    assert options[1]["name"].startswith("Emails  (since ")
