import io
import time
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from rich import get_console
from rich.console import Console, Group
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak import browser
from trak.browser import help_panel, overlay
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions import commands, listing
from trak.sessions.listing import (
    SHORTCUTS,
    ListFilters,
    browse,
    parse_day,
)
from trak.sessions.services import list_sessions, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

ROME = ZoneInfo("Europe/Rome")


@pytest.fixture(autouse=True)
def rome_time(monkeypatch):
    """Day filters use local midnight: pin the local time zone."""

    monkeypatch.setenv("TZ", "Europe/Rome")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """A time on October `day`, 2026, given in Rome time."""

    return datetime(2026, 10, day, hour, minute, tzinfo=ROME).astimezone(UTC)


def make(db, start, hours=1, **fields):
    session = start_session(db, start=start, **fields)
    return stop_session(db, session, end=start + timedelta(hours=hours))


# list_sessions


def test_newest_first_with_total(db):
    old = make(db, at(10, 9))
    new = make(db, at(12, 9))
    middle = make(db, at(11, 9))

    sessions, total = list_sessions(db)

    assert sessions == [new, middle, old]
    assert total == 3


def test_pagination(db):
    made = [make(db, at(10, hour)) for hour in range(8, 13)]

    page, total = list_sessions(db, limit=2, offset=2)

    assert page == [made[2], made[1]]
    assert total == 5


def test_filter_by_project(db):
    website = add(db, Project(name="website"))
    mine = make(db, at(10, 9), project_fk=website.id)
    make(db, at(10, 10))

    assert list_sessions(db, project_fk=website.id) == ([mine], 1)


def test_filter_by_name_is_case_insensitive_and_partial(db):
    landing = make(db, at(10, 9), name="Landing page")
    make(db, at(10, 10), name="Emails")

    assert list_sessions(db, name="landing") == ([landing], 1)


def test_filter_by_start_range(db):
    make(db, at(10, 9))
    inside = make(db, at(11, 9))
    make(db, at(12, 9))

    sessions, total = list_sessions(db, start_from=at(11, 0), start_until=at(12, 0))

    assert (sessions, total) == ([inside], 1)


# trak sessions list


def test_filter_by_customer_directly_or_through_the_project(db):
    acme = add(db, Customer(name="ACME"))
    other = add(db, Customer(name="Other"))
    acme_project = add(db, Project(name="website", customer_fk=acme.id))
    other_project = add(db, Project(name="app", customer_fk=other.id))
    direct = make(db, at(10, 9), customer_fk=acme.id)
    through_project = make(db, at(10, 10), project_fk=acme_project.id)
    make(db, at(10, 11), project_fk=other_project.id)
    make(db, at(10, 12), customer_fk=other.id)
    make(db, at(10, 13))

    sessions, total = list_sessions(db, customer_fk=acme.id)

    assert (sessions, total) == ([through_project, direct], 2)


def test_list_shows_a_table(cli_db):
    customer = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="website", customer_fk=customer.id))
    make(cli_db, at(10, 9, 30), hours=1.5, name="Landing page", project_fk=website.id)
    start_session(cli_db, name="Emails", start=datetime.now(UTC) - timedelta(minutes=5))

    result = runner.invoke(app, ["sessions", "list"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    emails = next(line for line in lines if "Emails" in line)
    landing = next(line for line in lines if "Landing page" in line)
    assert lines.index(emails) < lines.index(landing)
    assert "running" in emails
    for cell in ("website", "ACME", "2026-10-10 09:30", "11:00", "1h 30m"):
        assert cell in landing
    assert "Page 1 of 1 · 2 sessions" in result.output


def test_list_paginates(cli_db):
    for hour in range(8, 13):
        make(cli_db, at(10, hour), name=f"at {hour}")

    first = runner.invoke(app, ["sessions", "list", "--per-page", "2"])
    last = runner.invoke(app, ["sessions", "list", "--per-page", "2", "--page", "3"])

    assert "at 12" in first.output and "at 11" in first.output
    assert "at 10" not in first.output
    assert "Page 1 of 3 · 5 sessions · next: --page 2" in first.output
    assert "at 8" in last.output
    assert "Page 3 of 3" in last.output and "next" not in last.output


def test_list_page_out_of_range(cli_db):
    make(cli_db, at(10, 9))

    result = runner.invoke(app, ["sessions", "list", "--page", "2"])

    assert result.exit_code == 1
    assert "This page doesn't exist" in result.output


def test_list_without_sessions(cli_db):
    result = runner.invoke(app, ["sessions", "list"])

    assert result.exit_code == 0, result.output
    assert "No sessions" in result.output


def test_list_by_date_uses_local_days(cli_db):
    # 00:30 in Rome is still the previous day in UTC.
    make(cli_db, at(11, 0, 30), name="after")
    make(cli_db, at(10, 23, 30), name="before")

    result = runner.invoke(app, ["sessions", "list", "--date", "2026-10-11"])

    assert result.exit_code == 0, result.output
    assert "after" in result.output
    assert "before" not in result.output


def test_list_from_to_is_inclusive(cli_db):
    for day in (9, 10, 11, 12):
        make(cli_db, at(day, 12), name=f"day {day}")

    result = runner.invoke(
        app, ["sessions", "list", "--from", "2026-10-10", "--to", "2026-10-11"]
    )

    assert result.exit_code == 0, result.output
    assert "day 10" in result.output and "day 11" in result.output
    assert "day 9" not in result.output and "day 12" not in result.output


def test_list_date_conflicts_with_range(cli_db):
    result = runner.invoke(
        app, ["sessions", "list", "--date", "2026-10-10", "--from", "2026-10-01"]
    )

    assert result.exit_code == 1
    assert "Conflicting dates" in result.output


def test_list_by_project_and_name(cli_db):
    website = add(cli_db, Project(name="website"))
    make(cli_db, at(10, 9), name="Landing page", project_fk=website.id)
    make(cli_db, at(10, 10), name="Landing page")
    make(cli_db, at(10, 11), name="Emails", project_fk=website.id)

    result = runner.invoke(app, ["sessions", "list", "-p", "website", "-n", "landing"])

    assert result.exit_code == 0, result.output
    assert "1 session" in result.output
    assert "Emails" not in result.output


def test_list_includes_archived_projects(cli_db):
    old = add(cli_db, Project(name="old", archived=True))
    make(cli_db, at(10, 9), name="Archived work", project_fk=old.id)

    result = runner.invoke(app, ["sessions", "list", "--project", "old"])

    assert result.exit_code == 0, result.output
    assert "Archived work" in result.output


def test_list_by_customer(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="website", customer_fk=acme.id))
    make(cli_db, at(10, 9), name="Direct", customer_fk=acme.id)
    make(cli_db, at(10, 10), name="Through", project_fk=website.id)
    make(cli_db, at(10, 11), name="Unrelated")

    result = runner.invoke(app, ["sessions", "list", "--customer", "ACME"])

    assert result.exit_code == 0, result.output
    assert "Direct" in result.output and "Through" in result.output
    assert "Unrelated" not in result.output


def test_list_unknown_customer(cli_db):
    add(cli_db, Customer(name="ACME"))

    result = runner.invoke(app, ["sessions", "list", "-c", "nope"])

    assert result.exit_code == 1
    assert "This customer doesn't exist" in result.output
    assert "ACME" in result.output


def test_list_ambiguous_customer(cli_db):
    add(cli_db, Customer(name="ACME"))
    add(cli_db, Customer(name="ACME"))

    result = runner.invoke(app, ["sessions", "list", "-c", "ACME"])

    assert result.exit_code == 1
    assert "Ambiguous customer" in result.output


def test_list_unknown_project(cli_db):
    result = runner.invoke(app, ["sessions", "list", "--project", "nope"])

    assert result.exit_code == 1
    assert "This project doesn't exist" in result.output


# interactive browser


def keys(*pressed: str):
    """A key reader that types `pressed`, then fails if read again."""

    remaining = list(pressed)

    def read_key() -> str:
        assert remaining, "the browser read more keys than the test typed"
        return remaining.pop(0)

    return read_key


def filter_lines(output: str) -> list[str]:
    """The filter bar of every screen the browser drew."""

    return [line for line in output.splitlines() if line.startswith("Filters: ")]


def page_lines(output: str) -> list[str]:
    return [
        line.split(" · ?")[0]
        for line in output.splitlines()
        if line.startswith("Page ")
    ]


@pytest.mark.parametrize(
    ("next_key", "previous_key"),
    [("l", "h"), ("\x1b[C", "\x1b[D"), ("\x06", "\x02")],
    ids=["hl", "arrows", "ctrl-f/b"],
)
def test_browse_pages(db, capsys, next_key, previous_key):
    for hour in range(8, 13):
        make(db, at(10, hour), name=f"at {hour}")

    browse(
        db,
        FakePrompter(),
        ListFilters(per_page=2),
        read_key=keys(next_key, next_key, previous_key, "q"),
    )

    assert page_lines(capsys.readouterr().out) == [
        "Page 1 of 3 · 5 sessions",
        "Page 2 of 3 · 5 sessions",
        "Page 3 of 3 · 5 sessions",
        "Page 2 of 3 · 5 sessions",
    ]


def test_browse_first_and_last_page(db, capsys):
    for hour in range(8, 13):
        make(db, at(10, hour), name=f"at {hour}")

    browse(db, FakePrompter(), ListFilters(per_page=2), read_key=keys("G", "g", "q"))

    assert page_lines(capsys.readouterr().out) == [
        "Page 1 of 3 · 5 sessions",
        "Page 3 of 3 · 5 sessions",
        "Page 1 of 3 · 5 sessions",
    ]


def test_browse_quits_on_esc_typed_with_the_next_key(db, capsys):
    # A fast Esc can arrive glued to the next key: it's still an Esc.
    browse(db, FakePrompter(), ListFilters(), read_key=keys("\x1bq"))


def test_browse_hides_the_cursor_and_restores_it(db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        get_console(), "show_cursor", lambda show=True: calls.append(show)
    )

    browse(db, FakePrompter(), ListFilters(), read_key=keys("q"))

    assert calls[0] is False and calls[-1] is True


def test_browse_restores_the_cursor_on_ctrl_c(db, monkeypatch):
    calls = []
    monkeypatch.setattr(
        get_console(), "show_cursor", lambda show=True: calls.append(show)
    )

    def interrupted() -> str:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        browse(db, FakePrompter(), ListFilters(), read_key=interrupted)

    assert calls[-1] is True


@pytest.mark.parametrize("key", ["/", "p", "c", "d"])
def test_going_back_from_a_filter_keeps_the_filters(db, capsys, key):
    make(db, at(10, 9), name="Landing page")

    browse(
        db,
        FakePrompter(PromptCancelled()),
        ListFilters(name="landing"),
        read_key=keys(key, "q"),
    )

    assert set(filter_lines(capsys.readouterr().out)) == {'Filters: name: "landing"'}


def test_browse_ignores_keys_that_do_nothing(db, capsys):
    make(db, at(10, 9))

    # One page, no filters: paging, clear and unknown keys are ignored.
    browse(
        db,
        FakePrompter(),
        ListFilters(),
        read_key=keys("l", "h", "g", "G", "x", "z", "\x1b"),
    )

    assert page_lines(capsys.readouterr().out) == ["Page 1 of 1 · 1 session"]


def test_browse_filters_are_above_the_table(db, capsys):
    make(db, at(10, 9), name="Landing page")

    browse(db, FakePrompter(), ListFilters(name="landing"), read_key=keys("q"))

    lines = capsys.readouterr().out.splitlines()
    assert lines.index('Filters: name: "landing"') < next(
        i for i, line in enumerate(lines) if "Landing page" in line
    )


def test_browse_filters_stack_and_clear(db, capsys):
    website = add(db, Project(name="website"))
    make(db, at(10, 9), name="Landing page", project_fk=website.id)
    make(db, at(11, 9), name="Landing page")
    make(db, at(11, 10), name="Emails", project_fk=website.id)
    prompter = FakePrompter("landing", "website", "A single day", "2026-10-10")

    browse(db, prompter, ListFilters(), read_key=keys("/", "p", "d", "x", "q"))

    output = capsys.readouterr().out
    # Each edit draws the bar twice: above the prompt, then above the table.
    assert list(dict.fromkeys(filter_lines(output))) == [
        "Filters: none",
        'Filters: name: "landing"',
        'Filters: project: website · name: "landing"',
        'Filters: project: website · name: "landing" · date: 2026-10-10',
    ]
    assert filter_lines(output)[-1] == "Filters: none"
    assert "Page 1 of 1 · 1 session · ?" in output


def test_browse_filter_by_customer(db, capsys):
    acme = add(db, Customer(name="ACME"))
    add(db, Customer(name="Other"))
    make(db, at(10, 9), name="For ACME", customer_fk=acme.id)
    make(db, at(10, 10), name="For nobody")

    browse(
        db,
        FakePrompter("ACME", "Any customer"),
        ListFilters(),
        read_key=keys("c", "c", "q"),
    )

    output = capsys.readouterr().out
    assert list(dict.fromkeys(filter_lines(output))) == [
        "Filters: none",
        "Filters: customer: ACME",
    ]
    assert filter_lines(output)[-1] == "Filters: none"
    acme_screen = output.split("Filters: customer: ACME")[1]
    assert "For ACME" in acme_screen and "For nobody" not in acme_screen


def test_browse_date_range_is_inclusive_and_ordered(db, capsys):
    for day in (9, 10, 11, 12):
        make(db, at(day, 12), name=f"day {day}")
    # From/To typed the wrong way around: they get swapped.
    prompter = FakePrompter("A range", "2026-10-11", "2026-10-10")

    browse(db, prompter, ListFilters(), read_key=keys("d", "q"))

    output = capsys.readouterr().out
    assert filter_lines(output)[-1] == "Filters: from 2026-10-10 to 2026-10-11"
    last_screen = output.split("from 2026-10-10 to 2026-10-11")[-1]
    assert "day 10" in last_screen and "day 11" in last_screen
    assert "day 9" not in last_screen and "day 12" not in last_screen


def test_browse_any_project_and_any_date_remove_filters(db, capsys):
    website = add(db, Project(name="website"))
    filters = ListFilters(project=website, since=date(2026, 10, 1))
    prompter = FakePrompter("Any project", "Any date")

    browse(db, prompter, filters, read_key=keys("p", "d", "q"))

    assert filter_lines(capsys.readouterr().out)[-1] == "Filters: none"


def test_browse_filtering_goes_back_to_the_first_page(db, capsys):
    for hour in range(8, 13):
        make(db, at(10, hour), name=f"at {hour}")

    browse(
        db, FakePrompter("at"), ListFilters(per_page=2), read_key=keys("n", "/", "q")
    )

    assert page_lines(capsys.readouterr().out)[-1] == "Page 1 of 3 · 5 sessions"


def test_browse_clamps_a_page_out_of_range(db, capsys):
    make(db, at(10, 9))

    browse(db, FakePrompter(), ListFilters(page=9), read_key=keys("q"))

    assert "Page 1 of 1 · 1 session" in capsys.readouterr().out


def test_browse_without_matches(db, capsys):
    browse(db, FakePrompter(), ListFilters(name="nothing"), read_key=keys("q"))

    assert "No session matches these filters" in capsys.readouterr().out


def test_help_lists_every_shortcut_and_any_key_closes_it(db, capsys):
    make(db, at(10, 9), name="Landing page")

    browse(db, FakePrompter(), ListFilters(), read_key=keys("?", "x", "q"))

    output = capsys.readouterr().out
    help_screen = output.split("Shortcuts")[1].split("any key to close")[0]
    for _, _, _, description in SHORTCUTS:
        assert description in help_screen
    assert "l  →  Ctrl-f" in help_screen and "q  Esc" in help_screen
    # The help is drawn over the page, which is still there around it.
    assert "Landing page" in output.split("Shortcuts")[1]
    # After closing it the page is drawn again.
    assert page_lines(output.split("any key to close")[-1]) == [
        "Page 1 of 1 · 1 session"
    ]


@pytest.mark.parametrize("width", [40, 120])
def test_help_overlay_fits_the_terminal(width):
    out = io.StringIO()
    console = Console(file=out, width=width, height=30)

    overlay(console, Group(*["x" * width] * 5), help_panel(SHORTCUTS))

    lines = out.getvalue().splitlines()
    assert "Shortcuts" in out.getvalue()
    assert all(len(line) <= width for line in lines)
    assert len(lines) >= 5


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("2026-10-10", date(2026, 10, 10)),
        (" Today ", datetime.now().date()),
        ("yesterday", datetime.now().date() - timedelta(days=1)),
    ],
)
def test_parse_day(value, expected):
    assert parse_day(value) == expected


def test_parse_day_rejects_garbage():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_day("10/10/2026")


# interactive vs plain


def test_list_browses_in_a_terminal(interactive, monkeypatch, cli_db):
    website = add(cli_db, Project(name="website"))
    seen = {}

    def fake_browse(db, prompter, filters):
        seen["filters"] = filters

    monkeypatch.setattr(listing, "browse", fake_browse)
    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(FakePrompter()))

    acme = add(cli_db, Customer(name="ACME"))
    result = runner.invoke(
        app,
        [
            "sessions",
            "list",
            "-p",
            "website",
            "-c",
            "ACME",
            "-n",
            "landing",
            "-d",
            "2026-10-10",
        ],
    )

    assert result.exit_code == 0, result.output
    filters = seen["filters"]
    assert (filters.project.id, filters.customer.id) == (website.id, acme.id)
    assert (filters.name, filters.since, filters.until) == (
        "landing",
        date(2026, 10, 10),
        date(2026, 10, 10),
    )


def test_list_plain_prints_once_even_in_a_terminal(interactive, monkeypatch, cli_db):
    make(cli_db, at(10, 9), name="Landing page")
    monkeypatch.setattr(listing, "browse", lambda *a: pytest.fail("should not browse"))

    result = runner.invoke(app, ["sessions", "list", "--plain"])

    assert result.exit_code == 0, result.output
    assert "Landing page" in result.output


def test_list_ctrl_c_exits_cleanly(interactive, monkeypatch, cli_db):
    def interrupted() -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(browser, "getchar", interrupted)
    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(FakePrompter()))

    result = runner.invoke(app, ["sessions", "list"])

    assert result.exit_code == 0, result.output
