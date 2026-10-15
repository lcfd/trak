"""`trak sessions show` in a terminal: the session and its project's sessions."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePrompter, FakeScreen, add
from trak import clipboard, tui, views
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import start_session, stop_session
from trak.sessions.view import SessionView
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def make(db, name: str, days: int = 0, hours: float = 1, **fields) -> Session:
    start = START - timedelta(days=days)
    session = start_session(db, name=name, start=start, **fields)
    return stop_session(db, session, end=start + timedelta(hours=hours))


@pytest.fixture
def website(cli_db):
    """website with three sessions (newest first: Hero, Docs, Old), and Other."""

    project = add(cli_db, Project(name="website"))
    category = add(cli_db, Category(name="Design"))
    tag = add(cli_db, Tag(name="billable"))
    make(cli_db, "Old", days=3, project_fk=project.id)
    make(cli_db, "Docs", days=1, project_fk=project.id)
    make(
        cli_db,
        "Hero",
        project_fk=project.id,
        category_fk=category.id,
        tag_fks=[tag.id],
    )
    make(cli_db, "Other")
    cli_db.commit()
    return cli_db


def view(cli_db, session_id: int, *keys, width=120, height=30):
    screen = FakeScreen([*keys], width, height)
    shown = SessionView(cli_db.get_bind(), session_id)
    shown.loop(screen)
    return shown, screen


def test_two_panes_the_session_and_its_project(website):
    _, screen = view(website, 3, "q")

    top = screen.last.splitlines()[1]
    assert "[1] Session" in top and "[2] Sessions of website" in top
    assert "3" in next(l for l in screen.last.splitlines() if "│ Id " in l)
    assert "billable" in next(l for l in screen.last.splitlines() if "Tags " in l)
    assert "Project time  3h 0m in 3 sessions" in screen.last
    # Every session of the project, the shown one marked; not the others.
    assert "Hero" in next(line for line in screen.last.splitlines() if "▸ " in line)
    for name in ("Docs", "Old"):
        assert name in screen.last
    assert "Other" not in screen.last
    assert "Design #billable" in screen.last


def test_enter_opens_a_session_of_the_project_and_esc_goes_back(website):
    shown, screen = view(website, 3, "2", "j", "\r", tui.ESC, "q")

    after_enter, after_esc = screen.frames[3], screen.frames[4]
    assert "Docs" in after_enter.splitlines()[2]
    assert "Esc back" in after_enter
    assert "Hero" in after_esc.splitlines()[2]
    assert shown.session_id == 3 and shown.history == []


def test_esc_without_history_quits(website):
    _, screen = view(website, 3, tui.ESC)

    assert len(screen.frames) == 1


@pytest.fixture
def copied(monkeypatch):
    texts = []
    monkeypatch.setattr(
        clipboard, "copy", lambda text, console=None: texts.append(text) or True
    )
    return texts


def test_the_focus_starts_on_the_session(website):
    _, screen = view(website, 3, "j", "\r", "q")

    assert "[1] Session" in screen.frames[0].splitlines()[1]
    assert "j/k move" not in screen.frames[0]
    # j and Enter do nothing on the details: still the same session.
    assert "Hero" in screen.last.splitlines()[2]


def test_y_copies_the_id_of_the_shown_session(website, copied):
    _, screen = view(website, 3, "y", "q")

    assert copied == ["3"]
    assert "Copied 3 · session" in screen.last
    assert "y copy session id" in screen.frames[0]


def test_y_on_the_list_copies_the_selected_session(website, copied):
    # Newest first: Hero (3), Docs (2), Old (1).
    _, screen = view(website, 3, "2", "j", "j", "y", "q")

    assert copied == ["1"]
    assert "Copied 1 · session" in screen.last


def test_y_follows_the_focus_in_a_goal(website, copied):
    from datetime import date

    from trak.goals.models import Goal
    from trak.goals.view import GoalView

    goal = add(
        website,
        Goal(
            project_fk=1, hours=10, start=date(2026, 10, 1), deadline=date(2026, 10, 31)
        ),
    )
    screen = FakeScreen(["y", "2", "j", "y", "q"], 120, 30)
    GoalView(website.get_bind(), goal.id).loop(screen)

    # [1]: the goal itself. [2]: the session under the cursor (Docs, the second).
    assert copied == [str(goal.id), "2"]
    assert "y copy goal id" in screen.frames[0]
    assert "y copy session id" in screen.frames[2]
    assert "Copied 1 · goal" in screen.frames[1]


def test_y_on_an_empty_list_copies_nothing(website, copied):
    # Session 4 has no project: its list is empty.
    _, screen = view(website, 4, "2", "y", "q")

    assert copied == []
    assert "No session selected" in screen.last


def test_y_without_a_clipboard_says_so(website, monkeypatch):
    monkeypatch.setattr(clipboard, "copy", lambda text, console=None: False)

    _, screen = view(website, 3, "y", "q")

    assert "No clipboard" in screen.last


def test_e_edits_in_place(website, monkeypatch):
    monkeypatch.setattr(
        commands,
        "make_prompter",
        lambda: nullcontext(FakePrompter("Name", "Hero 2", "Save")),
    )

    _, screen = view(website, 3, "e", "q")

    assert "Saved" in screen.last
    assert "Hero 2" in screen.last
    website.expire_all()
    assert website.get(Session, 3).name == "Hero 2"


def test_s_stops_a_running_session(website):
    running_id = start_session(website, name="Now", project_fk=1).id
    # Reading the id began a transaction: end it, or the view can't write.
    website.commit()

    _, screen = view(website, running_id, "s", "q")

    assert "Stopped" in screen.last
    website.expire_all()
    assert not website.get(Session, running_id).active


def test_a_session_without_project(website):
    _, screen = view(website, 4, "q")

    assert "This session has no project" in screen.last


def test_narrow_terminals_show_one_pane_with_tabs(website):
    _, screen = view(website, 3, "2", "q", width=70)

    first, second = screen.frames
    assert "[1] Session" in first and "Sessions of website" not in first
    assert "1 Session" in first.splitlines()[0]
    assert "Sessions of website" in second and "[1] Session" not in second


def test_question_mark_shows_the_shortcuts(website):
    _, screen = view(website, 3, "?", "x", "q")

    assert "Copy the id of what's focused" in screen.frames[1]


def test_show_command_opens_the_view_in_a_terminal(website, monkeypatch):
    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    screen = FakeScreen(["q"])
    monkeypatch.setattr(views, "open_screen", lambda: nullcontext(screen))

    result = runner.invoke(app, ["sessions", "3"])

    assert result.exit_code == 0, result.output
    assert "[2] Sessions of website" in screen.last


def test_plain_prints_even_in_a_terminal(website, monkeypatch):
    monkeypatch.setattr(commands, "is_interactive", lambda: True)

    result = runner.invoke(app, ["sessions", "show", "3", "--plain"])

    assert result.exit_code == 0, result.output
    assert "Session #3" in result.output and "billable" in result.output


def test_clipboard_falls_back_to_osc_52(monkeypatch):
    from io import StringIO

    from rich.console import Console

    monkeypatch.setattr(clipboard.shutil, "which", lambda name: None)
    file = StringIO()

    assert clipboard.copy("42", Console(file=file, force_terminal=True))
    assert file.getvalue() == "\x1b]52;c;NDI=\a"
    assert not clipboard.copy("42", Console(file=StringIO()))
