from datetime import UTC, date, datetime, timedelta

import pytest
from rich.console import Console
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak.goals import listing
from trak.goals.commands import ask_edits, parse_date, parse_hours
from trak.goals.display import (
    format_days_left,
    pace_text,
    print_reminder,
    to_go_text,
)
from trak.goals.listing import GoalFilters, browse
from trak.goals.models import Goal
from trak.goals.services import (
    create_goal,
    goal_progress,
    list_goals,
    upcoming_goals,
    update_goal,
)
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions.services import local_midnight, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

TODAY = datetime.now().date()


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def track(db, project: Project, hours: float, day: date) -> None:
    start = local_midnight(day) + timedelta(hours=9)
    session = start_session(db, start=start, project_fk=project.id)
    stop_session(db, session, end=start + timedelta(hours=hours))


def goal(db, project: Project, hours=10, days=10, start=None, name="") -> Goal:
    return add(
        db,
        Goal(
            project_fk=project.id,
            name=name,
            hours=hours,
            start=start or TODAY,
            deadline=TODAY + timedelta(days=days),
        ),
    )


# services


def test_create_goal_starts_today(db):
    website = add(db, Project(name="website"))

    created = create_goal(
        db, project_fk=website.id, hours=40, deadline=date(2099, 1, 1), name=" Launch "
    )

    assert (created.hours, created.name, created.start) == (40, "Launch", TODAY)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"hours": 0}, "at least 1 hour"),
        ({"start": date(2026, 2, 1)}, "can't come before its start"),
    ],
)
def test_create_goal_rejects_invalid_fields(db, fields, message):
    website = add(db, Project(name="website"))
    fields = {"hours": 5, "deadline": date(2026, 1, 31), **fields}

    with pytest.raises(ValueError, match=message):
        create_goal(db, project_fk=website.id, **fields)


def test_update_goal(db):
    website = add(db, Project(name="website"))
    g = goal(db, website)

    update_goal(db, g, hours=20, name=" v2 ")

    db.refresh(g)
    assert (g.hours, g.name) == (20, "v2")
    with pytest.raises(ValueError, match="before its start"):
        update_goal(db, g, deadline=TODAY - timedelta(days=1))
    with pytest.raises(ValueError, match="Can't edit id"):
        update_goal(db, g, id=9)


def test_list_goals_nearest_first_without_past_ones(db):
    website = add(db, Project(name="website"))
    app_ = add(db, Project(name="app"))
    later = goal(db, website, days=20)
    sooner = goal(db, app_, days=0)
    past = goal(db, website, days=-1, start=TODAY - timedelta(days=5))

    def ids(**filters):
        return [g.id for g in list_goals(db, **filters)[0]]

    assert ids() == [sooner.id, later.id]
    assert ids(past=True) == [past.id, sooner.id, later.id]
    assert ids(project_fk=website.id) == [later.id]
    assert [g.id for g in upcoming_goals(db)] == [sooner.id, later.id]
    page, total = list_goals(db, limit=1, offset=1)
    assert ([g.id for g in page], total) == ([later.id], 2)


def test_progress_counts_the_project_sessions_from_start_to_deadline(db):
    website = add(db, Project(name="website"))
    other = add(db, Project(name="other"))
    start = date(2026, 10, 1)
    g = add(
        db,
        Goal(project_fk=website.id, hours=10, start=start, deadline=date(2026, 10, 31)),
    )
    track(db, website, 2, start)
    track(db, website, 3, date(2026, 10, 31))
    track(db, website, 8, date(2026, 9, 30))  # before the start
    track(db, website, 8, date(2026, 11, 1))  # after the deadline
    track(db, other, 8, date(2026, 10, 5))  # another project

    now = local_midnight(date(2026, 10, 21)) + timedelta(hours=12)
    progress = goal_progress(db, g, now=now)

    assert progress.tracked == timedelta(hours=5)
    assert progress.days_left == 10
    assert not progress.reached
    assert to_go_text(progress) == "5h 0m to go"


def test_progress_counts_running_sessions_until_now(db):
    website = add(db, Project(name="website"))
    g = goal(db, website, hours=1)
    now = datetime.now(UTC)
    start_session(db, project_fk=website.id, start=now - timedelta(minutes=90))

    progress = goal_progress(db, g, now=now)

    assert progress.reached
    assert "reached" in to_go_text(progress)


def test_remaining_time_adds_up_with_the_tracked_minutes(db):
    website = add(db, Project(name="website"))
    g = goal(db, website, hours=1)
    now = datetime.now(UTC)
    start_session(db, project_fk=website.id, start=now - timedelta(seconds=30))

    # 0h 0m tracked: 1h 0m to go, not 0h 59m.
    assert to_go_text(goal_progress(db, g, now=now)) == "1h 0m to go"


@pytest.mark.parametrize(
    ("days", "text"),
    [(2, "2 days left"), (1, "1 day left"), (0, "due today"), (-3, "ended 3 days ago")],
)
def test_format_days_left(days, text):
    assert format_days_left(days) == text


def test_parse_date():
    on = date(2026, 10, 14)
    assert parse_date("2026-12-01", on) == date(2026, 12, 1)
    assert parse_date(" Today ", on) == on
    assert parse_date("tomorrow", on) == date(2026, 10, 15)
    assert parse_date("+30", on) == date(2026, 11, 13)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_date("next week", on)


def test_parse_hours():
    assert parse_hours(" 40 ") == 40
    for value in ("0", "1.5", ""):
        with pytest.raises(ValueError, match="1 or more"):
            parse_hours(value)


# the reminder in the menu


def test_reminder_shows_upcoming_goals(db):
    website = add(db, Project(name="website"))
    goal(db, website, hours=40, days=16, name="Launch")
    goal(db, website, days=-1, start=TODAY - timedelta(days=5), name="Old")
    console = Console(record=True, width=120)

    print_reminder(console, db)

    text = console.export_text()
    assert "Goals" in text
    assert "website · Launch" in text and "0h 0m of 40h" in text
    assert "0h 0m of 40h tracked" in text and "0%" in text
    assert "5 workdays needed, ~2h 21m a day" in text
    deadline = TODAY + timedelta(days=16)
    assert f"16 days left, by {deadline:%a %d %b}" in text
    assert "Old" not in text


def test_reminder_without_goals_prints_nothing(db):
    console = Console(record=True)

    print_reminder(console, db)

    assert console.export_text() == ""


def test_menu_shows_the_goals_above_the_list(interactive, answers, cli_db):
    website = add(cli_db, Project(name="website"))
    goal(cli_db, website, hours=40, days=3)
    answers(PromptCancelled())

    result = invoke(cli_db)

    assert result.exit_code == 0, result.output
    assert "Goals" in result.output and "3 days left" in result.output


# trak goals create


def test_create_with_options(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(
        cli_db, "goals", "create", "website", "-H", "40", "--by", "+30", "-n", "Launch"
    )

    assert result.exit_code == 0, result.output
    assert "website · Launch" in result.output and "created" in result.output
    [created] = cli_db.exec(select(Goal)).all()
    assert (created.hours, created.start) == (40, TODAY)
    assert created.deadline == TODAY + timedelta(days=30)


def test_create_from_a_day(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(
        cli_db, "goals", "create", "website", "-H", "5", "-b", "2026-10-31",
        "-f", "2026-10-01",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    [created] = cli_db.exec(select(Goal)).all()
    assert (created.start, created.deadline) == (date(2026, 10, 1), date(2026, 10, 31))


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-H", "5"], "Give it the hours and the deadline"),
        (["--by", "+3"], "Give it the hours and the deadline"),
        (["-H", "5", "--by", "soon"], "Use YYYY-MM-DD"),
        (["-H", "5", "--by", "today", "-f", "tomorrow"], "before its start"),
    ],
)
def test_create_with_invalid_options(cli_db, args, message):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "goals", "create", "website", *args)

    assert result.exit_code == 1
    assert message in result.output
    assert not cli_db.exec(select(Goal)).all()


def test_create_for_an_unknown_project(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "goals", "create", "nope", "-H", "5", "--by", "+3")

    assert result.exit_code == 1
    assert "This project doesn't exist" in result.output


def test_create_without_projects(cli_db):
    result = invoke(cli_db, "goals", "create", "website", "-H", "5", "--by", "+3")

    assert result.exit_code == 1
    assert "trak projects create" in result.output


def test_create_without_project_asks_every_field(interactive, answers, cli_db):
    add(cli_db, Project(name="app"))
    website = add(cli_db, Project(name="website"))
    answers("website", "Launch", "40", "", "+10")

    result = invoke(cli_db, "goals", "create")

    assert result.exit_code == 0, result.output
    [created] = cli_db.exec(select(Goal)).all()
    assert (created.project_fk, created.name, created.hours) == (
        website.id,
        "Launch",
        40,
    )
    assert (created.start, created.deadline) == (TODAY, TODAY + timedelta(days=10))


def test_create_without_project_offers_the_project_end(interactive, answers, cli_db):
    end = TODAY + timedelta(days=20)
    add(cli_db, Project(name="website", end=end))
    fake = answers("website", "", "40", "", str(end))

    result = invoke(cli_db, "goals", "create")

    assert result.exit_code == 0, result.output
    assert fake.values["Deadline"] == str(end)
    [created] = cli_db.exec(select(Goal)).all()
    assert created.deadline == end


def test_create_deadline_defaults_to_the_project_end(cli_db):
    add(cli_db, Project(name="website", end=TODAY + timedelta(days=20)))

    result = invoke(cli_db, "goals", "create", "website", "-H", "40")

    assert result.exit_code == 0, result.output
    [created] = cli_db.exec(select(Goal)).all()
    assert created.deadline == TODAY + timedelta(days=20)


def test_create_needs_a_deadline_without_a_project_end(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "goals", "create", "website", "-H", "40")

    assert result.exit_code == 1
    assert "Give it the hours and the deadline" in result.output


def test_create_without_project_not_confirmed(interactive, answers, cli_db):
    add(cli_db, Project(name="website"))
    answers("website", "", "40", "", "+10", confirm=False)

    result = invoke(cli_db, "goals", "create")

    assert result.exit_code == 1
    assert "No goal was created" in result.output
    assert not cli_db.exec(select(Goal)).all()


def test_create_without_project_needs_a_terminal(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "goals", "create")

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


@pytest.mark.parametrize(
    ("hours", "tracked", "days", "text"),
    [
        # 40h in 17 days (today and the deadline included).
        (40, 0, 16, "5 workdays needed, ~2h 21m a day"),
        (40, 12.5, 16, "3.4 workdays needed, ~1h 37m a day"),
        (10, 2, 7, "1 workday needed, ~1h 0m a day"),
        (10, 6, 7, "0.5 workdays needed, ~30m a day"),
        (10, 0, 0, "1.2 workdays needed, ~10h 0m a day"),
    ],
)
def test_pace_relates_the_time_to_go_to_the_days_left(db, hours, tracked, days, text):
    website = add(db, Project(name="website"))
    g = goal(db, website, hours=hours, days=days)
    if tracked:
        track(db, website, tracked, TODAY)

    assert text in pace_text(goal_progress(db, g))


def test_pace_is_red_beyond_a_workday_a_day(db):
    website = add(db, Project(name="website"))
    tight = goal(db, website, hours=20, days=1)
    easy = goal(db, website, hours=16, days=1)

    assert pace_text(goal_progress(db, tight)).startswith("[bold red]")
    assert pace_text(goal_progress(db, easy)).startswith("[dim]")


def test_no_pace_once_reached_or_past(db):
    website = add(db, Project(name="website"))
    reached = goal(db, website, hours=2, days=5)
    track(db, website, 3, TODAY)
    past = goal(db, website, days=-1, start=TODAY - timedelta(days=5))

    assert pace_text(goal_progress(db, reached)) is None
    assert pace_text(goal_progress(db, past)) is None


# trak goals show


def test_goals_id_shows_the_goal(cli_db):
    website = add(cli_db, Project(name="website"))
    g = goal(cli_db, website, hours=10, days=5, name="Launch")
    track(cli_db, website, 2.5, TODAY)

    result = invoke(cli_db, "goals", str(g.id))

    assert result.exit_code == 0, result.output
    assert f"Goal #{g.id}" in result.output
    for text in ("website", "Launch", "10h", "2h 30m of 10h", "7h 30m to go"):
        assert text in result.output
    assert "5 days left" in result.output
    assert f'"trak goals edit {g.id}"' in result.output


def test_show_unknown_goal(cli_db):
    result = invoke(cli_db, "goals", "7")

    assert result.exit_code == 1
    assert "There's no goal #7" in result.output


def test_show_picks_among_past_goals_too(interactive, answers, monkeypatch, cli_db):
    website = add(cli_db, Project(name="website"))
    old_id = goal(cli_db, website, days=-1, start=TODAY - timedelta(days=5)).id
    seen = {}

    def fake_browse(db, prompter, filters, pick=False, title=""):
        seen["filters"], seen["pick"] = filters, pick
        return db.get(Goal, old_id)

    monkeypatch.setattr(listing, "browse", fake_browse)
    answers()

    result = invoke(cli_db, "goals", "show")

    assert result.exit_code == 0, result.output
    assert seen["pick"] and seen["filters"].past
    assert "ended 1 day ago" in result.output


# trak goals edit


def test_ask_edits(db):
    website = add(db, Project(name="website"))
    app_ = add(db, Project(name="app"))
    g = goal(db, website, hours=10, days=10)

    prompter = FakePrompter(
        "Project", "app",
        "Hours", "10",  # same value: not a change
        "Deadline", "+20",
        "Name", "v2",
        "Save",
    )  # fmt: skip

    changes = ask_edits(db, prompter, g)

    assert changes == {
        "project_fk": app_.id,
        "deadline": TODAY + timedelta(days=20),
        "name": "v2",
    }


def test_edit_by_id(interactive, answers, cli_db):
    website = add(cli_db, Project(name="website"))
    g = goal(cli_db, website, hours=10)
    answers("Hours", "25", "Save")

    result = invoke(cli_db, "goals", "edit", str(g.id))

    assert result.exit_code == 0, result.output
    assert "saved" in result.output
    cli_db.refresh(g)
    assert g.hours == 25


def test_edit_discarding_saves_nothing(interactive, answers, cli_db):
    website = add(cli_db, Project(name="website"))
    g = goal(cli_db, website, hours=10)
    answers("Hours", "25", PromptCancelled())

    result = invoke(cli_db, "goals", "edit", str(g.id))

    assert result.exit_code == 1
    assert "No changes were saved" in result.output
    cli_db.refresh(g)
    assert g.hours == 10


def test_edit_needs_a_terminal(cli_db):
    website = add(cli_db, Project(name="website"))
    g = goal(cli_db, website)

    result = invoke(cli_db, "goals", "edit", str(g.id))

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak goals list


def test_goals_alone_lists_the_upcoming_ones(cli_db):
    website = add(cli_db, Project(name="website"))
    goal(cli_db, website, hours=40, days=3, name="Launch")
    goal(cli_db, website, days=-1, start=TODAY - timedelta(days=5), name="Old")

    result = invoke(cli_db, "goals")

    assert result.exit_code == 0, result.output
    assert "Launch" in result.output and "0h 0m of 40h" in result.output
    assert "3 days left" in result.output
    assert "Old" not in result.output
    assert "Page 1 of 1 · 1 goal" in result.output


def test_list_with_past_and_project(cli_db):
    website = add(cli_db, Project(name="website"))
    other = add(cli_db, Project(name="other"))
    goal(cli_db, website, days=-1, start=TODAY - timedelta(days=5), name="Old")
    goal(cli_db, other, name="Elsewhere")

    result = invoke(cli_db, "goals", "list", "-a", "-p", "website")

    assert result.exit_code == 0, result.output
    assert "Old" in result.output and "ended 1 day ago" in result.output
    assert "Elsewhere" not in result.output


def test_list_without_goals(cli_db):
    result = invoke(cli_db, "goals", "list")

    assert result.exit_code == 0
    assert "No goal matches these filters" in result.output


def keys(*pressed: str):
    remaining = list(pressed)
    return lambda: remaining.pop(0)


def test_browse_toggles_past_and_filters_by_project(db, capsys):
    website = add(db, Project(name="website"))
    other = add(db, Project(name="other"))
    goal(db, website, name="Launch")
    goal(db, website, days=-1, start=TODAY - timedelta(days=5), name="Old")
    goal(db, other, name="Elsewhere")

    browse(db, FakePrompter("website"), GoalFilters(), read_key=keys("a", "p", "q"))

    screens = capsys.readouterr().out.split("Goals\n")
    assert "Old" not in screens[1]
    assert "Filters: with past" in screens[2] and "Old" in screens[2]
    last = screens[-1]
    assert "project: website · with past" in last
    assert "Elsewhere" not in last and "Launch" in last


def test_browse_picks_a_goal(db):
    website = add(db, Project(name="website"))
    goal(db, website, days=9)
    sooner = goal(db, website, days=2)

    picked = browse(db, FakePrompter(), GoalFilters(), read_key=keys("\r"), pick=True)

    assert picked.id == sooner.id
