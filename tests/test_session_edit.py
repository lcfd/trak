from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions import listing
from trak.sessions.editing import ask_edits, field_rows, parse_time
from trak.sessions.listing import ListFilters, browse
from trak.sessions.models import Category, Session
from trak.sessions.services import start_session, stop_session, update_session
from trak.typer_app import app

runner = CliRunner()

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def local(text: str) -> datetime:
    """A "YYYY-MM-DD HH:MM" typed in local time, as UTC."""

    return datetime.strptime(text, "%Y-%m-%d %H:%M").astimezone().astimezone(UTC)


def make(db, start: str = "2026-10-10 09:00", hours: float = 1, **fields) -> Session:
    session = start_session(db, start=local(start), **fields)
    return stop_session(db, session, end=session.start + timedelta(hours=hours))


# update_session


def test_update_session_changes_fields(db):
    session = make(db, name="Old")
    project = add(db, Project(name="website"))

    update_session(db, session, name="  New  ", project_fk=project.id)

    db.refresh(session)
    assert (session.name, session.project_fk) == ("New", project.id)


def test_update_session_end_stops_an_active_session(db):
    session = start_session(db, start=NOW - timedelta(hours=2))

    update_session(db, session, end=NOW - timedelta(hours=1))

    assert not session.active
    assert session.end == NOW - timedelta(hours=1)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"end": local("2026-10-10 08:00")}, "end before it starts"),
        ({"start": local("2026-10-10 11:00")}, "end before it starts"),
        ({"end": None}, "running again"),
        ({"active": True}, "Can't edit active"),
    ],
)
def test_update_session_rejects_invalid_changes(db, changes, message):
    session = make(db)

    with pytest.raises(ValueError, match=message):
        update_session(db, session, **changes)


# parse_time


def test_parse_time_empty_means_now():
    assert parse_time("", "end", now=NOW) == NOW


def test_parse_time_checks_the_order():
    with pytest.raises(ValueError, match="end before it starts"):
        parse_time("2026-10-10 08:00", "end", after=local("2026-10-10 09:00"))
    with pytest.raises(ValueError, match="start after it ends"):
        parse_time("2026-10-10 10:00", "start", before=local("2026-10-10 09:00"))


def test_parse_time_rejects_the_future():
    with pytest.raises(ValueError, match="can't end in the future"):
        parse_time("2099-01-01 00:00", "end")


# picking in the browser


def keys(*pressed: str):
    remaining = list(pressed)

    def read_key() -> str:
        assert remaining, "the browser read more keys than the test typed"
        return remaining.pop(0)

    return read_key


def test_browse_picks_the_highlighted_session(db):
    _, middle, _ = (
        make(db, f"2026-10-1{day} 09:00", name=f"day {day}") for day in (3, 2, 1)
    )

    picked = browse(
        db, FakePrompter(), ListFilters(), read_key=keys("j", "\r"), pick=True
    )

    assert picked.id == middle.id


def test_browse_cursor_moves_across_pages(db):
    for day in range(1, 6):
        make(db, f"2026-10-0{day} 09:00", name=f"day {day}")

    # Newest first, two per page: j j crosses to page 2, k comes back.
    picked = browse(
        db,
        FakePrompter(),
        ListFilters(per_page=2),
        read_key=keys("j", "j", "j", "k", "\n"),
        pick=True,
        fit=False,
    )

    assert picked.name == "day 3"


def test_browse_pick_on_an_empty_list_does_nothing(db):
    picked = browse(
        db, FakePrompter(), ListFilters(), read_key=keys("\r", "q"), pick=True
    )

    assert picked is None


# ask_edits


def test_ask_edits_returns_only_real_changes(db):
    session = make(db, name="Landing")
    website = add(db, Project(name="website"))

    prompter = FakePrompter(
        "Name", "Landing",  # same value: not a change
        "Project", "website",
        "Start", "2026-10-10 08:30",
        "End", "2026-10-10 11:00",
        "Save",
    )  # fmt: skip

    changes = ask_edits(db, prompter, session)

    assert changes == {
        "project_fk": website.id,
        "start": local("2026-10-10 08:30"),
        "end": local("2026-10-10 11:00"),
    }


def test_ask_edits_going_back_from_a_field_keeps_it(db):
    session = make(db, name="Landing")

    changes = ask_edits(db, FakePrompter("Name", PromptCancelled(), "Save"), session)

    assert changes == {}


def test_ask_edits_going_back_from_the_list_cancels(db):
    session = make(db)

    with pytest.raises(PromptCancelled):
        ask_edits(db, FakePrompter("Name", "New", PromptCancelled()), session)


def test_project_with_a_customer_replaces_the_session_customer(db):
    acme = add(db, Customer(name="ACME"))
    other = add(db, Customer(name="Other"))
    website = add(db, Project(name="website", customer_fk=acme.id))
    session = make(db, customer_fk=other.id)

    changes = ask_edits(db, FakePrompter("Project", "website", "Save"), session)

    assert changes == {"project_fk": website.id, "customer_fk": None}
    labels = [label for _, label, _ in field_rows(db, session, changes)]
    assert "Customer" not in labels
    assert ("project_fk", "Project", "website (ACME)") in field_rows(
        db, session, changes
    )


def test_field_rows_show_category_only_when_there_are_some(db):
    session = make(db)
    assert "Category" not in [label for _, label, _ in field_rows(db, session, {})]

    add(db, Category(name="Design"))
    assert "Category" in [label for _, label, _ in field_rows(db, session, {})]


def test_running_session_end_reads_running(db):
    session = start_session(db, start=NOW)

    assert field_rows(db, session, {})[-1] == ("end", "End", "running")


# trak sessions edit


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def test_edit_by_id(interactive, answers, cli_db):
    session = make(cli_db, name="Old")
    answers("Name", "New", "Save")

    result = invoke(cli_db, "sessions", "edit", str(session.id))

    assert result.exit_code == 0, result.output
    assert "saved" in result.output
    cli_db.refresh(session)
    assert session.name == "New"


def test_edit_unknown_id(interactive, cli_db):
    result = invoke(cli_db, "sessions", "edit", "42")

    assert result.exit_code == 1
    assert "There's no session #42" in result.output


def test_edit_picks_from_the_browser(interactive, answers, monkeypatch, cli_db):
    session = make(cli_db, name="Old")
    # Read it now: touching `session` mid-command would lock the database.
    session_id = session.id
    seen = {}

    def fake_browse(db, prompter, filters, pick=False, title=""):
        seen["pick"] = pick
        return db.get(Session, session_id)

    monkeypatch.setattr(listing, "browse", fake_browse)
    answers("Name", "New", "Save")

    result = invoke(cli_db, "sessions", "edit")

    assert result.exit_code == 0, result.output
    assert seen["pick"] is True
    cli_db.refresh(session)
    assert session.name == "New"


def test_edit_quitting_the_browser_cancels(interactive, answers, monkeypatch, cli_db):
    monkeypatch.setattr(listing, "browse", lambda *a, **k: None)
    answers()

    result = invoke(cli_db, "sessions", "edit")

    assert result.exit_code == 1
    assert "No session was edited" in result.output


def test_edit_discarding_saves_nothing(interactive, answers, cli_db):
    session = make(cli_db, name="Old")
    answers("Name", "New", PromptCancelled())

    result = invoke(cli_db, "sessions", "edit", str(session.id))

    assert result.exit_code == 1
    assert "No changes were saved" in result.output
    cli_db.refresh(session)
    assert session.name == "Old"


def test_edit_without_changes(interactive, answers, cli_db):
    session = make(cli_db)
    answers("Save")

    result = invoke(cli_db, "sessions", "edit", str(session.id))

    assert result.exit_code == 0, result.output
    assert "Nothing changed" in result.output


def test_edit_needs_a_terminal(cli_db):
    session = make(cli_db)

    result = invoke(cli_db, "sessions", "edit", str(session.id))

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak sessions


def test_sessions_alone_lists_sessions(cli_db):
    make(cli_db, name="Landing page")

    result = invoke(cli_db, "sessions")

    assert result.exit_code == 0, result.output
    assert "Landing page" in result.output
