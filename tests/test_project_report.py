import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner

from tests.fakes import add
from tests.test_sessions_list import keys
from trak.projects import report
from trak.projects.models import Project
from trak.projects.report import (
    Range,
    all_ranges,
    bar_cells,
    buckets,
    chart_top,
    choose_unit,
    daily_time,
    months_before,
    report_ranges,
)
from trak.prompts import ESC
from trak.sessions.services import start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

ROME = ZoneInfo("Europe/Rome")
TODAY = date(2026, 10, 14)  # a Wednesday
NOW = datetime(2026, 10, 14, 18, 0, tzinfo=ROME).astimezone(UTC)


@pytest.fixture(autouse=True)
def rome_time(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Rome")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ROME).astimezone(
        UTC
    )


def track(db, project, start: datetime, hours: float):
    session = start_session(db, start=start, project_fk=project.id)
    return stop_session(db, session, end=start + timedelta(hours=hours))


def by_key(ranges: list[Range]) -> dict[str, tuple[date, date]]:
    return {r.key: (r.start, r.end) for r in ranges}


def by_key_range(ranges: list[Range]) -> dict[str, Range]:
    return {r.key: r for r in ranges}


# Ranges


def test_months_before_clamps_to_the_month_end():
    assert months_before(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_before(date(2026, 1, 15), 3) == date(2025, 10, 15)


def test_all_ranges():
    ranges = by_key(all_ranges(date(2024, 5, 1), TODAY))

    assert ranges == {
        "all": (date(2024, 5, 1), TODAY),
        "year": (date(2025, 10, 15), TODAY),
        "6m": (date(2026, 4, 15), TODAY),
        "3m": (date(2026, 7, 15), TODAY),
        "30d": (date(2026, 9, 15), TODAY),
        "month": (date(2026, 10, 1), date(2026, 10, 31)),
        "last-week": (date(2026, 10, 5), date(2026, 10, 11)),
        "7d": (date(2026, 10, 8), TODAY),
        "week": (date(2026, 10, 12), date(2026, 10, 18)),
    }


def test_since_the_start_runs_to_an_end_still_to_come():
    ranges = by_key(all_ranges(date(2024, 5, 1), TODAY, date(2026, 12, 31)))

    assert ranges["all"] == (date(2024, 5, 1), date(2026, 12, 31))
    # An end already past doesn't cut the range: sessions can come after it.
    ranges = by_key(all_ranges(date(2024, 5, 1), TODAY, date(2025, 1, 1)))
    assert ranges["all"] == (date(2024, 5, 1), TODAY)


def test_project_ranges_start_at_the_project_start(db):
    project = add(db, Project(name="website", start=date(2026, 9, 1)))
    track(db, project, at(date(2026, 10, 6), 9), 1)

    [since_start, *_] = report.project_ranges(
        project, report.load_sessions(db, project), NOW
    )

    assert (since_start.start, since_start.end) == (date(2026, 9, 1), TODAY)


def test_project_ranges_start_at_a_session_before_the_project_start(db):
    project = add(
        db, Project(name="website", start=date(2026, 10, 1), end=date(2026, 11, 30))
    )
    track(db, project, at(date(2026, 9, 20), 9), 1)

    [since_start, *_] = report.project_ranges(
        project, report.load_sessions(db, project), NOW
    )

    assert (since_start.start, since_start.end) == (
        date(2026, 9, 20),
        date(2026, 11, 30),
    )


def test_ranges_are_only_the_ones_that_make_sense():
    # Started on Tue 6 Oct: older ranges would all be "Since the start".
    keys_ = [r.key for r in report_ranges(date(2026, 10, 6), TODAY)]

    assert keys_ == ["all", "month", "last-week", "7d", "week"]


def test_a_project_started_today_still_shows_the_days_left():
    # This month and this week run past today.
    assert [r.key for r in report_ranges(TODAY, TODAY)] == ["all", "month", "week"]


def test_ranges_after_the_last_session_are_left_out(db):
    # Untouched since 2022: every range but "Since the start" would be empty.
    project = add(db, Project(name="website", start=date(2021, 7, 3)))
    track(db, project, at(date(2022, 6, 10), 9), 1)

    ranges = report.project_ranges(project, report.load_sessions(db, project), NOW)

    assert [r.key for r in ranges] == ["all"]


def test_ranges_up_to_the_last_session_stay(db):
    project = add(db, Project(name="website"))
    track(db, project, at(date(2025, 1, 10), 9), 1)
    track(db, project, at(date(2026, 9, 15), 9), 1)

    ranges = report.project_ranges(project, report.load_sessions(db, project), NOW)

    assert [r.key for r in ranges] == ["all", "year", "6m", "3m", "30d"]


def test_a_running_session_keeps_the_recent_ranges(db):
    project = add(db, Project(name="website"))
    track(db, project, at(date(2025, 1, 10), 9), 1)
    start_session(db, start=at(TODAY, 17), project_fk=project.id)

    ranges = report.project_ranges(project, report.load_sessions(db, project), NOW)

    assert "week" in [r.key for r in ranges]


def test_a_project_ending_later_keeps_the_days_left(db):
    project = add(db, Project(name="website", end=date(2026, 12, 31)))
    track(db, project, at(date(2025, 1, 10), 9), 1)

    ranges = report.project_ranges(project, report.load_sessions(db, project), NOW)

    assert {"month", "week"} <= {r.key for r in ranges}


# Time per day and per bucket


def test_daily_time_splits_sessions_at_local_midnight(db):
    project = add(db, Project(name="website"))
    track(db, project, at(date(2026, 10, 12), 23), 2)
    running = start_session(db, start=at(TODAY, 17), project_fk=project.id)

    daily = daily_time(
        report.load_sessions(db, project), date(2026, 10, 12), TODAY, NOW
    )

    assert running.active
    assert daily == {
        date(2026, 10, 12): timedelta(hours=1),
        date(2026, 10, 13): timedelta(hours=1),
        TODAY: timedelta(hours=1),
    }


def test_daily_time_clips_to_the_range(db):
    project = add(db, Project(name="website"))
    track(db, project, at(date(2026, 10, 11), 23), 2)

    daily = daily_time(
        report.load_sessions(db, project), date(2026, 10, 12), TODAY, NOW
    )

    assert sum(daily.values(), timedelta()) == timedelta(hours=1)


def test_buckets_by_week_start_inside_the_range():
    daily = {
        date(2026, 10, 1) + timedelta(days=i): timedelta(hours=1) for i in range(14)
    }

    weeks = buckets(daily, "week")

    assert [(b.start, b.time) for b in weeks] == [
        (date(2026, 10, 1), timedelta(hours=4)),  # Thu to Sun
        (date(2026, 10, 5), timedelta(hours=7)),
        (date(2026, 10, 12), timedelta(hours=3)),
    ]


@pytest.mark.parametrize(
    ("key", "width", "unit"),
    [
        ("month", 72, "day"),
        ("30d", 72, "day"),
        ("7d", 30, "day"),
        ("3m", 72, "week"),
        ("3m", 200, "day"),
        ("all", 100, "month"),
        ("all", 10, "year"),
    ],
)
def test_choose_unit_fits_the_width(key, width, unit):
    ranges = {r.key: r for r in all_ranges(date(2023, 1, 1), TODAY)}

    assert choose_unit(ranges[key], width) == unit


def test_chart_top_is_round():
    assert chart_top(timedelta(minutes=20)) == timedelta(minutes=30)
    assert chart_top(timedelta(hours=2, minutes=10)) == timedelta(hours=3)
    assert chart_top(timedelta(hours=33)) == timedelta(hours=34)


def test_bar_cells_from_the_top():
    top = timedelta(hours=4)

    assert bar_cells(timedelta(hours=2), top, 4) == [" ", " ", "█", "█"]
    assert bar_cells(timedelta(hours=1, minutes=30), top, 4) == [" ", " ", "▄", "█"]
    # A little time still shows.
    assert bar_cells(timedelta(minutes=1), top, 4) == [" ", " ", " ", "▁"]


# The command


def test_report_prints_without_a_terminal(cli_db, monkeypatch):
    monkeypatch.setattr(report, "datetime", FrozenNow)
    project = add(cli_db, Project(name="website", rate=50))
    track(cli_db, project, at(date(2026, 10, 13), 9), 2)
    track(cli_db, project, at(TODAY, 9), 1)
    track(cli_db, project, at(date(2026, 8, 3), 9), 4)

    result = runner.invoke(app, ["projects", "report", "1", "--range", "week"])

    assert result.exit_code == 0, result.output
    assert "This week" in result.output
    assert "3h 0m tracked in 2 sessions" in result.output
    assert "Busiest day: Tue 13 Oct 2026 · 2h 0m" in result.output
    assert "Earned: 150 at 50/h" in result.output
    assert "Tue 13" in result.output
    assert "q quit" not in result.output


def test_report_shows_every_day_of_the_range(cli_db, monkeypatch):
    monkeypatch.setattr(report, "datetime", FrozenNow)
    monkeypatch.setenv("COLUMNS", "80")
    project = add(cli_db, Project(name="website"))
    track(cli_db, project, at(date(2026, 10, 12), 9), 2)

    result = runner.invoke(app, ["projects", "report", "1", "--range", "week"])

    assert result.exit_code == 0, result.output
    assert "Mon 12 Oct 2026 → Sun 18 Oct 2026" in result.output
    assert "1 of 3 days worked · 2h 0m per day worked · 4 days left" in result.output
    # The empty Tuesday is there, and so are the days still to come.
    for label in ("Mon 12", "Tue 13", "Wed 14", "Sun 18"):
        assert label in result.output
    # Past days on a solid axis, the 4 to come on a dotted one.
    axis = next(line for line in result.output.splitlines() if "0└" in line)
    line = axis.strip().removeprefix("0└")
    solid, dotted = line.count("─"), line.count("┈")
    assert line == "─" * solid + "┈" * dotted
    assert solid * 4 == dotted * 3


def test_report_runs_to_the_project_end(cli_db, monkeypatch):
    monkeypatch.setattr(report, "datetime", FrozenNow)
    add(
        cli_db,
        Project(name="website", start=date(2026, 10, 1), end=date(2026, 10, 31)),
    )

    result = runner.invoke(app, ["projects", "report", "1"])

    assert result.exit_code == 0, result.output
    assert "website · 2026-10-01 → 2026-10-31" in result.output
    assert "Thu 01 Oct 2026 → Sat 31 Oct 2026" in result.output


def test_report_draws_the_chart_even_when_nothing_is_tracked(cli_db, monkeypatch):
    monkeypatch.setattr(report, "datetime", FrozenNow)
    add(cli_db, Project(name="website"))

    result = runner.invoke(app, ["projects", "report", "1", "--range", "week"])

    assert result.exit_code == 0, result.output
    assert "0h 0m tracked" in result.output
    assert "0└" in result.output
    assert "Sun 18" in result.output


def test_report_of_a_missing_project(cli_db):
    result = runner.invoke(app, ["projects", "report", "7"])

    assert result.exit_code == 1
    assert "There's no project #7" in result.output


def test_report_needs_a_terminal_to_pick(cli_db):
    result = runner.invoke(app, ["projects", "report"])

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


class FrozenNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.astimezone().replace(tzinfo=None)


def headings(output: str) -> list[str]:
    """The range heading of every screen drawn."""

    lines = (line.strip("│ ") for line in output.splitlines())
    return [line.split(" · ")[0] for line in lines if " → " in line]


def test_show_switches_ranges(db, capsys):
    project = add(db, Project(name="website"))
    track(db, project, at(date(2024, 1, 5), 9), 2)
    # Running: every range has time, so every range is shown.
    start_session(db, start=at(TODAY, 17), project_fk=project.id)

    report.show(
        db,
        project,
        read_key=keys("\t", "]", "[", "9", "]", "1", "[", "3", "9", "q"),
        now=lambda: NOW,
    )

    # Every range is shown: All, 1y... "]" past the last and "[" before the
    # first are ignored, as is "9" (there are 9 ranges: it's the last one).
    assert headings(capsys.readouterr().out) == [
        "Since the start",
        "Last year",
        "Last 6 months",
        "Last year",
        "This week",
        "Since the start",
        "Last 6 months",
        "This week",
    ]


def test_zoom_range_is_the_bar_one_unit_down():
    year = by_key_range(all_ranges(date(2023, 1, 1), TODAY))["year"]

    # The first month starts with the range, the last one ends with it.
    october = report.zoom_range(
        year, report.Bucket(date(2025, 10, 15), timedelta()), "month"
    )
    assert (october.start, october.end, october.unit) == (
        date(2025, 10, 15),
        date(2025, 10, 31),
        "week",
    )
    assert october.label == "Last year › October 2025"
    now = report.zoom_range(
        year, report.Bucket(date(2026, 10, 1), timedelta()), "month"
    )
    assert (now.start, now.end) == (date(2026, 10, 1), TODAY)

    week = report.zoom_range(now, report.Bucket(date(2026, 10, 5), timedelta()), "week")
    assert (week.start, week.end, week.unit) == (
        date(2026, 10, 5),
        date(2026, 10, 11),
        "day",
    )
    assert week.label == "Last year › October 2026 › Week of Mon 05 Oct 2026"
    # A day is as far as it goes.
    assert report.zoom_range(week, report.Bucket(TODAY, timedelta()), "day") is None


def test_show_zooms_into_a_bar_and_out(db, capsys):
    project = add(db, Project(name="website", start=date(2024, 1, 1)))
    track(db, project, at(date(2026, 10, 6), 9), 2)
    track(db, project, at(date(2026, 10, 13), 9), 1)

    report.show(
        db,
        project,
        "year",
        # Today's month, today's week; a day goes no further; back; the
        # week before, its first day; back, back to the year, Esc quits.
        read_key=keys("\r", "\r", "\r", ESC, "h", "\r", ESC, ESC, ESC),
        now=lambda: NOW,
    )

    out = capsys.readouterr().out
    assert headings(out) == [
        "Last year",
        "Last year › October 2026",
        "Last year › October 2026 › Week of Mon 12 Oct 2026",
        "Last year › October 2026",
        "Last year › October 2026",
        "Last year › October 2026 › Week of Mon 05 Oct 2026",
        "Last year › October 2026",
        "Last year",
    ]
    assert "October 2026 · 3h 0m · Enter: its weeks" in out
    assert "Wed 14 Oct 2026 · 0h 0m" in out
    assert "Week of Mon 05 Oct 2026 · 2h 0m · Enter: its days" in out
    assert "Mon 05 Oct 2026 · 0h 0m" in out


def test_show_moves_across_bars(db, capsys):
    project = add(db, Project(name="website"))

    report.show(
        db,
        project,
        "week",
        # Today is Wednesday: Tue, Mon, nothing before Mon; the last, Sunday.
        read_key=keys("h", "h", "h", "G", "l", "g", "q"),
        now=lambda: NOW,
    )

    selected = [
        line.strip("│ ").split(" · ")[0]
        for line in capsys.readouterr().out.splitlines()
        if "▌" in line
    ]
    assert selected == [
        "▌ Wed 14 Oct 2026",
        "▌ Tue 13 Oct 2026",
        "▌ Mon 12 Oct 2026",
        "▌ Sun 18 Oct 2026",
        "▌ Mon 12 Oct 2026",
    ]


def test_show_help_and_esc(db, capsys):
    project = add(db, Project(name="website"))

    report.show(db, project, read_key=keys("?", "x", "\x1b"), now=lambda: NOW)

    assert "Next range" in capsys.readouterr().out


def test_show_refreshes(db, capsys):
    project = add(db, Project(name="website"))
    pressed = iter(["r", "q"])

    def read_key() -> str:
        key = next(pressed)
        if key == "r":
            track(db, project, at(TODAY, 9), 1)
        return key

    report.show(db, project, read_key=read_key, now=lambda: NOW)

    out = capsys.readouterr().out
    assert "0h 0m tracked" in out
    assert "1h 0m tracked in 1 session" in out


def test_report_command_opens_the_report_in_a_terminal(
    cli_db, monkeypatch, interactive
):
    project = add(cli_db, Project(name="website"))
    shown = []
    monkeypatch.setattr(
        report, "show", lambda db, p, key, custom: shown.append((p.id, key, custom))
    )

    result = runner.invoke(app, ["projects", "report", str(project.id), "-r", "7d"])

    assert result.exit_code == 0, result.output
    assert shown == [(project.id, "7d", None)]


def test_report_command_opens_the_asked_days(cli_db, monkeypatch, interactive):
    project = add(cli_db, Project(name="website", start=date(2026, 1, 1)))
    shown = []
    monkeypatch.setattr(report, "show", lambda db, p, key, custom: shown.append(custom))

    result = runner.invoke(
        app, ["projects", "report", str(project.id), "--to", "2026-03-31"]
    )

    assert result.exit_code == 0, result.output
    # From the project's first day by default.
    [custom] = shown
    assert (custom.key, custom.start, custom.end) == (
        "custom",
        date(2026, 1, 1),
        date(2026, 3, 31),
    )


def test_custom_days_come_first_in_the_tabs(db, capsys):
    project = add(db, Project(name="website"))
    custom = report.asked_range(db, project, "2026-10-01", "2026-10-07", NOW)

    report.show(db, project, read_key=keys("\t", "q"), now=lambda: NOW, custom=custom)

    assert headings(capsys.readouterr().out) == ["Custom", "Since the start"]


def test_from_must_be_a_day(db):
    project = add(db, Project(name="website"))

    with pytest.raises(ValueError, match="--from: use YYYY-MM-DD"):
        report.asked_range(db, project, "soon", None, NOW)


def test_tabs_get_short_when_they_dont_fit():
    ranges = all_ranges(date(2023, 1, 1), TODAY)

    assert report.tabs(ranges, 0, 200).plain.startswith(" Since the start ")
    assert report.tabs(ranges, 0, 60).plain.startswith(" All ")
