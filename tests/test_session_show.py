from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

from tests.fakes import add
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.sessions import listing
from trak.sessions.models import Session, Tag
from trak.sessions.services import start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def make(db, hours: float = 1.5, **fields) -> Session:
    session = start_session(db, start=START, **fields)
    return stop_session(db, session, end=START + timedelta(hours=hours))


def test_sessions_id_shows_the_session(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="website", customer_fk=acme.id))
    tag = add(cli_db, Tag(name="billable"))
    session = make(cli_db, name="Landing", project_fk=website.id, tag_fk=tag.id)

    result = invoke(cli_db, "sessions", str(session.id))

    assert result.exit_code == 0, result.output
    assert f"Session #{session.id}" in result.output
    for text in ("Landing", "website", "ACME (from the project)", "billable"):
        assert text in result.output
    assert f"{START.astimezone():%Y-%m-%d %H:%M}" in result.output
    assert "1h 30m" in result.output
    assert f'"trak sessions edit {session.id}"' in result.output


def test_show_is_the_same_as_the_id_alone(cli_db):
    session = make(cli_db, name="Landing")

    by_id = invoke(cli_db, "sessions", str(session.id))
    by_show = invoke(cli_db, "sessions", "show", str(session.id))

    assert by_show.exit_code == 0
    assert by_show.output == by_id.output


def test_show_a_running_session(cli_db):
    session = start_session(cli_db, start=START)

    result = invoke(cli_db, "sessions", str(session.id))

    assert result.exit_code == 0, result.output
    assert "running" in result.output
    # A session without a name, project, ... shows dashes.
    assert "Name" in result.output and "—" in result.output


def test_show_unknown_id(cli_db):
    result = invoke(cli_db, "sessions", "42")

    assert result.exit_code == 1
    assert "There's no session #42" in result.output
    assert '"trak sessions show"' in result.output


def test_unknown_command_is_still_an_error(cli_db):
    result = invoke(cli_db, "sessions", "nope")

    assert result.exit_code == 2
    assert "No such command" in result.output


def test_show_without_id_picks_from_the_browser(
    interactive, answers, monkeypatch, cli_db
):
    session = make(cli_db, name="Picked")
    session_id = session.id
    seen = {}

    def fake_browse(db, prompter, filters, pick=False, title=""):
        seen["pick"], seen["title"] = pick, title
        return db.get(Session, session_id)

    monkeypatch.setattr(listing, "browse", fake_browse)
    answers()

    result = invoke(cli_db, "sessions", "show")

    assert result.exit_code == 0, result.output
    assert seen == {"pick": True, "title": "Pick a session to show"}
    assert "Picked" in result.output


def test_show_without_id_quitting_the_browser(
    interactive, answers, monkeypatch, cli_db
):
    monkeypatch.setattr(listing, "browse", lambda *a, **k: None)
    answers()

    result = invoke(cli_db, "sessions", "show")

    assert result.exit_code == 1
    assert "No session was shown" in result.output


def test_show_without_id_needs_a_terminal(cli_db):
    result = invoke(cli_db, "sessions", "show")

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


def test_sessions_help_mentions_the_id(cli_db):
    result = invoke(cli_db, "sessions", "--help")

    assert result.exit_code == 0
    assert "ID | COMMAND" in result.output
