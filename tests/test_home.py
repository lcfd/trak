"""The home of a bare `trak`: three panes, full screen, driven by keys."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from rich.console import Console
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakeScreen
from trak import browser, clipboard, config, dev_bar, tui, views
from trak.goals.models import Goal
from trak.main import home, menu
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import start_session, stop_session, update_session
from trak.typer_app import app

runner = CliRunner()


@pytest.fixture
def screen(monkeypatch):
    """Run `trak` as in a terminal, typing `keys` (q at the end to quit)."""

    monkeypatch.setattr(commands, "is_interactive", lambda: True)

    def use(*keys, width=120, height=40):
        fake = FakeScreen(keys, width, height)
        monkeypatch.setattr(menu, "open_screen", lambda: nullcontext_of(fake))
        return fake

    return use


@contextmanager
def nullcontext_of(value):
    yield value


def trak():
    return runner.invoke(app, [])


def test_three_panes_with_the_focus_on_actions(screen):
    fake = screen("q")

    result = trak()

    assert result.exit_code == 0, result.output
    top = fake.last.splitlines()[1]
    assert "[1] Goals" in top and "[2] Sessions" in top and "[3] Actions" in top
    assert top.index("Goals") < top.index("Sessions") < top.index("Actions")
    assert f"trak v{config.VERSION}" in fake.last.splitlines()[0]
    # The footer tells what the focused pane does.
    assert "Enter run" in fake.last.splitlines()[-1]


def test_actions_list_every_command(screen):
    fake = screen("q")

    trak()

    for path in ("start", "stop", "sessions list", "goals create", "help", "quit"):
        assert f"│ {path} " in fake.last
    # Hidden commands and the developer tools stay out.
    assert "dev fill" not in fake.last


def test_the_frame_fills_the_terminal_and_follows_resizes(screen):
    fake = screen(None, ("resize", 140, 30), ("resize", 100, 20), "q", width=120)

    result = trak()

    assert result.exit_code == 0, result.output
    # FakeScreen.draw checks every frame is exactly the terminal's size.
    sizes = [(len(f.splitlines()[0]), len(f.splitlines())) for f in fake.frames]
    assert sizes == [(120, 40), (120, 40), (140, 30), (100, 20)]


def test_a_narrow_terminal_shows_one_pane_with_tabs(screen):
    fake = screen("1", "q", width=70, height=20)

    trak()

    first, after_1 = fake.frames
    assert "[3] Actions" in first and "[1] Goals" not in first
    assert "1 Goals" in first.splitlines()[0] and "3 Actions" in first.splitlines()[0]
    assert "[1] Goals" in after_1 and "[3] Actions" not in after_1


def test_a_tiny_terminal_asks_for_more_room(screen):
    fake = screen("q", width=20, height=5)

    trak()

    assert "bigger" in fake.last


def test_numbers_and_h_l_move_the_focus(screen):
    fake = screen("1", "l", "h", "h", "\t", "q")

    trak()

    focused = [focused_pane(frame) for frame in fake.frames]
    assert focused == ["Actions", "Goals", "Sessions", "Goals", "Actions", "Goals"]


def focused_pane(frame: str) -> str:
    """The pane whose hints are in the footer."""

    footer = frame.splitlines()[-1]
    if "new goal" in footer:
        return "Goals"
    if "stop" in footer:
        return "Sessions"
    return "Actions"


def test_dev_mode_keeps_the_bar_on_top(screen, monkeypatch, tmp_path):
    fake = screen("q")
    monkeypatch.setenv(config.DEV_ENV_VAR, "1")

    trak()

    assert fake.last.splitlines()[0].startswith(" DEV MODE")
    assert len(fake.last.splitlines()) == 40


def test_without_a_terminal_prints_the_help():
    result = trak()

    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


def test_q_quits_and_ctrl_c_exits_130(screen, monkeypatch):
    screen("q")
    assert trak().exit_code == 0

    def interrupt(timeout=None):
        raise KeyboardInterrupt

    fake = screen()
    monkeypatch.setattr(fake, "read_key", interrupt)
    assert trak().exit_code == 130


# Goals and Sessions.


def seed(db):
    website = Project(name="website")
    db.add(website)
    db.commit()
    today = datetime.now().date()
    db.add(
        Goal(
            project_fk=website.id,
            hours=40,
            start=today,
            deadline=today + timedelta(days=16),
            name="Launch",
        )
    )
    db.add(
        Goal(
            project_fk=website.id,
            hours=1,
            start=today - timedelta(days=5),
            deadline=today - timedelta(days=1),
            name="Old",
        )
    )
    start = datetime.now(UTC) - timedelta(hours=2, minutes=5)
    running = start_session(db, project_fk=website.id, name="Design", start=start)
    stopped = start_session(db, name="Done", start=start - timedelta(days=1))
    stop_session(db, stopped, end=start - timedelta(days=1) - timedelta(minutes=-30))
    db.commit()
    return running, stopped


def test_goals_show_progress_and_days_left(screen, cli_db):
    seed(cli_db)
    fake = screen("q")

    trak()

    assert "website · Launch" in fake.last
    assert "16 days left" in fake.last
    assert "2h 5m of 40h · 37h 55m to go" in fake.last
    assert "4.7 workdays needed" in fake.last
    assert "Old" not in fake.last


def test_sessions_show_running_ones_first_then_by_day(screen, cli_db):
    seed(cli_db)
    fake = screen("q")

    trak()

    assert "Running (1)" in fake.last
    assert "● " in fake.last and "2h 5m  Design · website" in fake.last
    assert "Yesterday" in fake.last and "0h 30m  Done" in fake.last
    assert fake.last.index("Running") < fake.last.index("Yesterday")
    assert "● 1 running" in fake.last.splitlines()[0]


def test_empty_panes_say_how_to_fill_them(screen):
    fake = screen("q")

    trak()

    assert "No upcoming goals." in fake.last and "No sessions yet." in fake.last


def test_s_stops_the_running_session_in_place(screen, cli_db):
    running, _ = seed(cli_db)
    fake = screen("2", "s", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert fake.suspensions == 0
    assert "Stopped Design · website · 2h 5m" in fake.last
    cli_db.refresh(running)
    assert not running.active
    assert "Running (" not in fake.last


def test_s_on_a_stopped_session_does_nothing(screen, cli_db):
    seed(cli_db)
    fake = screen("2", "G", "s", "q")

    trak()

    assert "isn't running" in fake.last
    assert cli_db.exec(select(Session).where(Session.active)).one()


def test_enter_shows_the_session_then_comes_back(screen, cli_db, monkeypatch):
    seed(cli_db)
    # Enter runs `sessions show ID`, a full-screen view: q there comes back.
    view = FakeScreen(["q"])
    monkeypatch.setattr(views, "open_screen", lambda: nullcontext_of(view))
    fake = screen("2", "\r", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert fake.suspensions == 1
    assert "Design" in view.last and "[1] Session" in view.last
    assert "Press any key" not in result.output
    assert len(fake.frames) == 3


def test_sessions_show_their_category_and_tags(screen, cli_db):
    seed(cli_db)
    design = Category(name="Design")
    tag = Tag(name="billable")
    cli_db.add_all([design, tag])
    cli_db.commit()
    running = cli_db.exec(select(Session).where(Session.active)).one()
    update_session(cli_db, running, category_fk=design.id, tag_fks=[tag.id])
    # One pane at a time: room for the whole row.
    fake = screen("2", "q", width=90)

    trak()

    assert "Design · website  Design #billable" in fake.last


def test_q_after_a_command_quits(screen, cli_db):
    seed(cli_db)
    fake = screen("/", "status", "\r", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert "Running (1)" in result.output
    assert len(fake.frames) == 3


def test_e_edits_the_goal(screen, cli_db, monkeypatch):
    seed(cli_db)
    ran = []
    monkeypatch.setattr(
        home, "run_command", lambda ctx, cmd, path, args: ran.append((path, args))
    )
    screen("1", "e", "x", "q")

    trak()

    goal = cli_db.exec(select(Goal).where(Goal.name == "Launch")).one()
    assert ran == [("goals edit", [str(goal.id)])]


def test_n_starts_a_session_or_creates_a_goal(screen, cli_db, monkeypatch):
    ran = []
    monkeypatch.setattr(
        home, "run_command", lambda ctx, cmd, path, args: ran.append(path)
    )
    screen("2", "n", "x", "1", "n", "x", "q")

    trak()

    assert ran == ["start", "goals create"]


def test_y_copies_the_goal_session_or_command(screen, cli_db, monkeypatch):
    copied = []
    monkeypatch.setattr(
        clipboard, "copy", lambda text, console=None: copied.append(text) or True
    )
    running, stopped = seed(cli_db)
    running_id, stopped_id = running.id, stopped.id
    goal_id = cli_db.exec(select(Goal).where(Goal.name == "Launch")).one().id
    # Goals: the first one. Sessions: the running one, then the next. Actions:
    # the first command (start) as typed; help and quit copy nothing.
    fake = screen("1", "y", "2", "y", "j", "y", "3", "y", "G", "y", "q")

    trak()

    assert copied == [str(goal_id), str(running_id), str(stopped_id), "trak start"]
    assert "Copied trak start" in fake.frames[8]


# Actions.


def test_enter_runs_the_action_with_its_defaults(screen, cli_db):
    fake = screen("\r", "x", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert fake.suspensions == 1
    [session] = cli_db.exec(select(Session)).all()
    assert session.active


def test_the_filter_ranks_abbreviations_first(screen, cli_db, monkeypatch):
    ran = []
    monkeypatch.setattr(
        home, "run_command", lambda ctx, cmd, path, args: ran.append(path)
    )
    fake = screen("/", "s", "e", "\r", "x", "q")

    trak()

    assert ran == ["sessions edit"]
    filtered = fake.frames[3]
    assert "/se▏" in filtered
    rows = [line for line in filtered.splitlines() if "edit" in line or "list" in line]
    assert "sessions edit" in rows[0]
    # After running it, the whole list is back, on the command that ran.
    assert "/se" not in fake.last and "goals edit" in fake.last


def test_typing_in_the_filter_never_switches_pane(screen):
    fake = screen("/", "1", "2", "q", tui.ESC, tui.ESC, "q")

    trak()

    assert "/12q▏" in fake.frames[4]
    assert "Enter run" in fake.frames[-1]
    assert "/12q" not in fake.frames[-1]


def test_full_screen_views_come_back_without_a_key(screen, monkeypatch):
    monkeypatch.setattr(browser, "getchar", lambda: "q")
    fake = screen("/", "sl", "\r", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert "No session matches" in result.output
    assert "Press any key" not in result.output
    assert fake.suspensions == 1


def test_errors_of_a_command_stay_on_its_screen(screen, monkeypatch):
    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    fake = screen("/", "stop", "\r", "x", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert (
        "No active session" in result.output or "not running" in result.output.lower()
    )
    assert len(fake.frames) >= 2


def test_help_and_quit_actions(screen):
    screen("/", "help", "\r", "x", "q")
    result = trak()
    assert result.exit_code == 0 and "Usage" in result.output

    fake = screen("G", "\r")
    assert trak().exit_code == 0
    assert len(fake.frames) == 2


def test_question_mark_shows_the_shortcuts_over_the_home(screen):
    fake = screen("?", "x", "q")

    trak()

    assert (
        "Shortcuts" in fake.frames[1] and "Stop the running session" in fake.frames[1]
    )
    assert "Shortcuts" not in fake.frames[2]


# Terminal helpers.


@pytest.mark.parametrize(
    ("data", "keys"),
    [
        ("jjk", ["j", "j", "k"]),
        ("\x1b[A\x1b[B", ["\x1b[A", "\x1b[B"]),
        ("\x1bj", ["\x1b", "j"]),
        ("\x1b", ["\x1b"]),
        ("\x1b[1;5C", ["\x1b[1;5C"]),
        ("\x1bOP", ["\x1bOP"]),
        ("\x1b[Z", ["\x1b[Z"]),
    ],
)
def test_split_keys(data, keys):
    assert tui.split_keys(data) == keys


def test_spread_puts_the_right_part_flush_right():
    text = tui.spread(tui.Text("a long left part"), tui.Text("right"), 14)

    assert text.plain == "a long … right"
    assert len(text.plain) == 14


def test_render_has_exactly_the_size():
    frame = tui.render(Console(), tui.Text("one\ntwo"), 10, 5)

    assert len(frame) == 5
    assert all(tui.Segment.get_line_length(line) == 10 for line in frame)


def test_lines_keep_the_style_of_the_whole_text(monkeypatch, tmp_path):
    # The dev bar is a Text styled as a whole: its background must stay.
    monkeypatch.setattr(dev_bar, "dev_db_path", tmp_path / "dev.sqlite3")

    [segment] = tui.line(dev_bar.bar(30), 30)

    assert segment.style.bgcolor.name == "green" and segment.style.bold


def test_dev_bar_fits_one_line(monkeypatch, tmp_path):
    monkeypatch.setattr(dev_bar, "dev_db_path", tmp_path / ("x" * 60))
    assert tui.Segment.get_line_length(tui.line(dev_bar.bar(30), 30)) == 30


def test_a_usage_error_of_a_command_stays_on_its_screen(screen, cli_db, monkeypatch):
    # Enter on a goal runs `goals show ID`: give it an id that isn't a number.
    seed(cli_db)
    original = home.run_command
    monkeypatch.setattr(
        home,
        "run_command",
        lambda ctx, cmd, path, args: original(ctx, cmd, path, ["not-a-number"]),
    )
    # A full-screen view: back without a key.
    fake = screen("1", "\r", "q")

    result = trak()

    assert result.exit_code == 0, result.output
    assert "not-a-number" in result.output
    assert len(fake.frames) == 3
