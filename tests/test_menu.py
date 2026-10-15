from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter
from trak import browser, config
from trak.goals.models import Goal
from trak.main.menu import LOGO, command_score
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions import commands
from trak.sessions.models import Session
from trak.sessions.services import start_session, stop_session
from trak.typer_app import app

runner = CliRunner()


@pytest.fixture
def prompter(monkeypatch):
    """Run `trak` as in a terminal, answering the menu with `answers`."""

    monkeypatch.setattr(commands, "is_interactive", lambda: True)

    def use(*answers):
        fake = FakePrompter(*answers)
        monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(fake))
        return fake

    return use


def test_menu_lists_every_command(prompter, monkeypatch):
    seen = []

    class Recording(FakePrompter):
        def ask(self, label, options, **kwargs):
            seen.extend(o["name"].split()[0:2] for o in options)
            assert kwargs["allow_filtering"] is True
            raise PromptCancelled

    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(Recording()))

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    names = [" ".join(words) for words in seen]
    assert "start Start" in names
    assert "stop Stop" in names
    assert "sessions list" in names
    assert names[-2:] == ["help Show", "quit Leave"]
    # Hidden commands, like the debug `test`, stay out of the menu.
    assert not any(name.startswith("test") for name in names)


def test_menu_runs_the_picked_command(prompter, cli_db):
    prompter("start ")

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "Start" in result.output
    [session] = cli_db.exec(select(Session)).all()
    assert session.active


def test_menu_runs_nested_commands(prompter, monkeypatch):
    prompter("sessions list")
    monkeypatch.setattr(browser, "getchar", lambda: "q")

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "No session matches" in result.output


def test_menu_shows_the_logo_above_the_list(prompter):
    prompter(PromptCancelled())

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert LOGO.strip("\n") in result.output
    assert f"v{config.VERSION}" in result.output


def test_help_entry_prints_the_help(prompter):
    prompter("help")

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "Usage" in result.output
    assert "sessions" in result.output


def test_quit_entry_exits_quietly(prompter):
    prompter("quit")

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "Usage" not in result.output
    assert "Cancelled" not in result.output


def test_going_back_exits_quietly(prompter):
    prompter(PromptCancelled())

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Cancelled" not in result.output


def test_ctrl_c_exits_130(prompter):
    prompter(SystemExit())

    result = runner.invoke(app, [])

    assert result.exit_code == 130


def test_without_a_terminal_prints_the_help():
    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "Usage" in result.output
    assert "start" in result.output


COMMANDS = [
    "start",
    "stop",
    "sessions list",
    "sessions show",
    "sessions edit",
    "projects list",
    "projects create",
    "projects edit",
    "customers list",
    "customers edit",
    "help",
    "quit",
]


def ranked(query: str) -> list[str]:
    scores = {path: command_score(query, path) for path in COMMANDS}
    matches = [path for path in COMMANDS if scores[path] is not None]
    return sorted(matches, key=lambda path: -scores[path])


@pytest.mark.parametrize(
    ("query", "best"),
    [
        ("sl", "sessions list"),
        ("se", "sessions edit"),
        ("pc", "projects create"),
        ("ce", "customers edit"),
        ("cl", "customers list"),
        ("sess li", "sessions list"),
        ("seli", "sessions list"),
        ("st", "start"),
        ("SL", "sessions list"),
    ],
)
def test_abbreviations_find_the_command_first(query, best):
    assert ranked(query)[0] == best


def test_a_later_word_matches_after_the_abbreviations():
    assert ranked("edit") == ["sessions edit", "projects edit", "customers edit"]


def test_letters_in_order_match_last():
    # "sl" abbreviates "sessions list", and is only in order in the others.
    assert ranked("sl") == ["sessions list", "projects list", "customers list"]
    assert command_score("tsp", "stop") is None


def test_description_matches_when_the_name_does_not():
    assert command_score("newest", "sessions list", "List sessions, newest first.")
    assert command_score("newest", "sessions list") is None


def test_menu_ranks_with_command_score(prompter, monkeypatch):
    seen = {}

    class Recording(FakePrompter):
        def ask(self, label, options, **kwargs):
            rank = kwargs["rank"]
            scored = [(rank("se", o), o["name"].split()[:2]) for o in options]
            seen["best"] = max((s, n) for s, n in scored if s is not None)[1]
            raise PromptCancelled

    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(Recording()))

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert seen["best"] == ["sessions", "edit"]


def test_menu_shows_the_running_sessions_above_the_goals(prompter, cli_db):
    website = Project(name="website")
    cli_db.add(website)
    cli_db.commit()
    today = datetime.now().date()
    cli_db.add(
        Goal(project_fk=website.id, hours=10, start=today, deadline=today, name="Ship")
    )
    start = datetime.now(UTC) - timedelta(hours=2, minutes=5)
    running = start_session(cli_db, project_fk=website.id, name="Design", start=start)
    stopped = start_session(cli_db, name="Done")
    stop_session(cli_db, stopped)
    cli_db.commit()
    prompter(PromptCancelled())

    result = runner.invoke(app, [])

    assert result.exit_code == 0, result.output
    assert "Running sessions (1)" in result.output
    assert "Design · website" in result.output and "2h 5m" in result.output
    assert f"#{running.id}" in result.output and "Done" not in result.output
    assert result.output.index("Running sessions") < result.output.index("Goals")


def test_menu_without_running_sessions_shows_no_section(prompter):
    prompter(PromptCancelled())

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Running sessions" not in result.output
