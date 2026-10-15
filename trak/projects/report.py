"""
`trak projects report`: the time tracked on a project, as a bar chart.

The report stays open: Tab switches the time range (since the start, last
year, ... this week), h/l select a bar, Enter zooms into it (a year shows its
months, a month its weeks, a week its days), Esc zooms out, `?` lists the
shortcuts, q quits. Each bar is the time tracked in a day; when the days don't
fit the terminal, a bar is a week, a month or a year instead.

Every day of the range has its bar, even an empty one, so skipped days show;
"this month" and "this week" run to their last day, with the days still to
come on a dotted axis.

"Since the start" runs from the project's start (or its first session, if
earlier) to its end, when that's still to come.

Sessions are split at local midnight, so a session from 23:00 to 01:00 counts
one hour on each day; running ones count until now.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any, Literal

from rich import get_console
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.text import Text
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import browser, clipboard, dev_bar, tui
from trak.dates import parse_date
from trak.output import seconds
from trak.projects.listing import format_dates
from trak.projects.models import Project
from trak.prompts import ESC
from trak.sessions.display import format_duration
from trak.sessions.models import Session
from trak.sessions.services import local_midnight

Unit = Literal["day", "week", "month", "year"]
UNITS: list[Unit] = ["day", "week", "month", "year"]


# Time ranges


@dataclass(frozen=True)
class Range:
    key: str
    label: str
    # For the tabs, when the labels don't fit.
    short: str
    # Both days included.
    start: date
    end: date
    # The time a bar holds; None for the smallest that fits.
    unit: Unit | None = None

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def months_before(day: date, months: int) -> date:
    """The same day `months` earlier, or the month's last day if it's shorter."""

    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    for candidate in range(day.day, 0, -1):
        try:
            return date(year, month, candidate)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def all_ranges(first: date, today: date, last: date | None = None) -> list[Range]:
    """
    Every range, from the longest. `first` is the project's first day (its
    start or its first session); `last` is its end, if any.
    """

    monday = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    month_end = months_before(month_start, -1) - timedelta(days=1)

    def trailing(months: int) -> date:
        return months_before(today, months) + timedelta(days=1)

    return [
        Range(
            "all",
            "Since the start",
            "All",
            min(first, today),
            max(last, today) if last else today,
        ),
        Range("year", "Last year", "1y", trailing(12), today),
        Range("6m", "Last 6 months", "6m", trailing(6), today),
        Range("3m", "Last 3 months", "3m", trailing(3), today),
        Range("30d", "Last 30 days", "30d", today - timedelta(days=29), today),
        Range("month", "This month", "Month", month_start, month_end),
        Range(
            "last-week",
            "Last week",
            "Last wk",
            monday - timedelta(days=7),
            monday - timedelta(days=1),
        ),
        Range("7d", "Last 7 days", "7d", today - timedelta(days=6), today),
        Range("week", "This week", "Week", monday, monday + timedelta(days=6)),
    ]


RANGE_KEYS = [r.key for r in all_ranges(date(2000, 1, 1), date(2000, 1, 1))]


def report_ranges(
    first: date, today: date, last: date | None = None, latest: date | None = None
) -> list[Range]:
    """
    The ranges worth showing: not the ones ending before the first day, nor
    the ones starting after `latest` (the project's last session, start or
    end: they'd be empty), nor the ones ending today that start on or before
    the first day (they'd be the same as "Since the start"). "This week" and
    "this month" end later, so they're worth it while the project goes on:
    they show the days left.
    """

    latest = latest or today
    since_start, *others = all_ranges(first, today, last)
    useful = [
        r
        for r in others
        if r.end >= first
        and r.start <= latest
        and not (r.end == today and r.start <= first)
    ]
    return [since_start, *useful]


# Time tracked per day, and per bucket (a day, week, month or year)


def daily_time(
    sessions: list[Session], start: date, end: date, now: datetime
) -> dict[date, timedelta]:
    """The time tracked on each local day from `start` to `end` (included)."""

    totals = {
        start + timedelta(days=i): timedelta() for i in range((end - start).days + 1)
    }
    range_start, range_end = (
        local_midnight(start),
        local_midnight(end + timedelta(days=1)),
    )
    for session in sessions:
        begin = max(session.start, range_start)
        finish = min(session.end or now, range_end)
        while begin < finish:
            day = begin.astimezone().date()
            midnight = local_midnight(day + timedelta(days=1))
            totals[day] += min(finish, midnight) - begin
            begin = midnight
    return totals


def bucket_of(day: date, unit: Unit) -> date:
    if unit == "day":
        return day
    if unit == "week":
        return day - timedelta(days=day.weekday())
    if unit == "month":
        return day.replace(day=1)
    return day.replace(month=1, day=1)


@dataclass
class Bucket:
    # The first day of the bucket within the range.
    start: date
    time: timedelta


def buckets(daily: dict[date, timedelta], unit: Unit) -> list[Bucket]:
    """The days grouped by `unit`, in order."""

    grouped: dict[date, Bucket] = {}
    for day in sorted(daily):
        key = bucket_of(day, unit)
        if key not in grouped:
            grouped[key] = Bucket(start=day, time=timedelta())
        grouped[key].time += daily[day]
    return list(grouped.values())


def bucket_end(day: date, unit: Unit) -> date:
    """The last day of the bucket holding `day`."""

    first = bucket_of(day, unit)
    following = {
        "day": first + timedelta(days=1),
        "week": first + timedelta(days=7),
        "month": months_before(first, -1),
        "year": first.replace(year=first.year + 1),
    }[unit]
    return following - timedelta(days=1)


def bucket_name(day: date, unit: Unit) -> str:
    """ "Mon 12 Oct 2026", "week of Mon 12 Oct 2026", "October 2026", "2026"."""

    return {
        "day": format_day(day),
        "week": f"week of {format_day(bucket_of(day, 'week'))}",
        "month": f"{day:%B %Y}",
        "year": f"{day:%Y}",
    }[unit]


# Enter on a bar shows its days one bar per the next unit down.
SMALLER: dict[Unit, Unit] = {"year": "month", "month": "week", "week": "day"}


def zoom_range(r: Range, bucket: Bucket, unit: Unit) -> Range | None:
    """The days of a bar of `r`, one bar per smaller unit; None for a day."""

    smaller = SMALLER.get(unit)
    if smaller is None:
        return None
    name = bucket_name(bucket.start, unit)
    return Range(
        "zoom",
        f"{r.label} › {name[0].upper()}{name[1:]}",
        r.short,
        bucket.start,
        min(bucket_end(bucket.start, unit), r.end),
        smaller,
    )


def count_buckets(r: Range, unit: Unit) -> int:
    return len({bucket_of(r.start + timedelta(days=i), unit) for i in range(r.days)})


# Each bar takes at least one column, plus one between bars; at most MAX_COLUMN.
MIN_COLUMN = 2
MAX_COLUMN = 8


def choose_unit(r: Range, width: int) -> Unit:
    """The smallest unit whose bars fit in `width` columns."""

    for unit in UNITS:
        if count_buckets(r, unit) * MIN_COLUMN <= width:
            return unit
    return "year"


# The report


@dataclass
class Report:
    project: Project
    range: Range
    today: date
    unit: Unit
    buckets: list[Bucket]
    total: timedelta
    sessions: int
    days_worked: int
    running: bool

    @property
    def days_so_far(self) -> int:
        """The range's days up to today."""

        return max(0, (min(self.range.end, self.today) - self.range.start).days + 1)

    def is_future(self, bucket: Bucket) -> bool:
        return bucket.start > self.today

    def index_of(self, day: date) -> int:
        """The bar holding `day` (the nearest one if it's out of the range)."""

        key = bucket_of(day, self.unit)
        for index, bucket in enumerate(self.buckets):
            if bucket_of(bucket.start, self.unit) >= key:
                return index
        return len(self.buckets) - 1


def load_sessions(db: DBSession, project: Project) -> list[Session]:
    statement = select(Session).where(Session.project_fk == project.id)
    return list(db.exec(statement.order_by(Session.start)))


def build_report(
    project: Project,
    sessions: list[Session],
    r: Range,
    width: int,
    now: datetime,
) -> Report:
    daily = daily_time(sessions, r.start, r.end, now)
    range_start, range_end = (
        local_midnight(r.start),
        local_midnight(r.end + timedelta(days=1)),
    )
    inside = [
        s for s in sessions if s.start < range_end and (s.end or now) > range_start
    ]
    unit = r.unit or choose_unit(r, width)
    return Report(
        project=project,
        range=r,
        today=now.astimezone().date(),
        unit=unit,
        buckets=buckets(daily, unit),
        total=sum(daily.values(), timedelta()),
        sessions=len(inside),
        days_worked=sum(1 for time in daily.values() if time),
        running=any(s.end is None for s in inside),
    )


# The chart

BLOCKS = " ▁▂▃▄▅▆▇█"

# Label formats, from the longest: the longest that fits under a bar wins.
LABELS: dict[Unit, list[str]] = {
    "day": ["%a %d", "%d"],
    "week": ["%d %b", "%d"],
    "month": ["%b %Y", "%b"],
    "year": ["%Y"],
}
# The line under the labels, written where it changes (unless the label has it).
CONTEXT: dict[Unit, str | None] = {
    "day": "%b",
    "week": "%b",
    "month": "%Y",
    "year": None,
}


def axis_label(time: timedelta) -> str:
    """ "45m", "1.5h", "12h"."""

    minutes = time.total_seconds() / 60
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = minutes / 60
    return f"{hours:.0f}h" if hours >= 10 or hours == int(hours) else f"{hours:.1f}h"


def chart_top(longest: timedelta) -> timedelta:
    """A round value at or above the longest bar: 15-minute steps, then hours."""

    minutes = longest.total_seconds() / 60
    if minutes <= 60:
        return timedelta(minutes=max(15, ceil(minutes / 15) * 15))
    hours = ceil(minutes / 60)
    if hours > 10:
        hours = ceil(hours / 2) * 2
    return timedelta(hours=hours)


def bar_cells(time: timedelta, top: timedelta, height: int) -> list[str]:
    """The bar's character on each row, from the top; a non-empty bar shows."""

    eighths = round(time / top * height * 8)
    if time and not eighths:
        eighths = 1
    cells = []
    for row in range(height - 1, -1, -1):
        filled = min(8, max(0, eighths - row * 8))
        cells.append(BLOCKS[filled])
    return cells


def place_labels(texts: list[str | None], column: int, width: int) -> str:
    """Write each text under its bar, skipping the ones that would overlap."""

    line = [" "] * width
    free = 0
    for index, text in enumerate(texts):
        position = index * column
        if not text or position < free or position + len(text) > width:
            continue
        line[position : position + len(text)] = text
        free = position + len(text) + 1
    return "".join(line).rstrip()


def x_labels(report: Report, column: int, width: int) -> list[str]:
    days = [bucket.start for bucket in report.buckets]
    formats = LABELS[report.unit]
    fitting = [f for f in formats if len(days[0].strftime(f)) < column]
    fmt = fitting[0] if fitting else formats[-1]
    size = len(days[0].strftime(fmt))
    # Label every `step` bars, so that the labels don't touch.
    step = 1 if fitting else ceil((size + 1) / column)
    lines = [
        place_labels(
            [d.strftime(fmt) if i % step == 0 else None for i, d in enumerate(days)],
            column,
            width,
        )
    ]

    context = CONTEXT[report.unit]
    if context and "%b" not in fmt and "%Y" not in fmt:
        texts: list[str | None] = []
        previous = None
        for d in days:
            value = d.strftime(context)
            texts.append(value if value != previous else None)
            previous = value
        lines.append(place_labels(texts, column, width))
    return lines


def chart(report: Report, width: int, height: int, selected: int | None = None) -> Text:
    """
    The bars with a y axis on the left and the labels under them; the
    `selected` bar stands out, its axis too (it may be empty).
    """

    longest = max((b.time for b in report.buckets), default=timedelta())
    top = chart_top(longest)
    marks = {0: axis_label(top), height // 2: axis_label(top / 2)}
    gutter = max(len(m) for m in marks.values()) + 2

    plot_width = width - gutter
    column = max(MIN_COLUMN, min(MAX_COLUMN, plot_width // max(1, len(report.buckets))))
    bar = column - 1
    columns = [bar_cells(b.time, top, height) for b in report.buckets]

    text = Text()
    for row in range(height):
        text.append(
            f"{marks.get(row, ''):>{gutter - 2}} ┤"
            if row in marks
            else " " * (gutter - 1) + "│",
            style="dim",
        )
        for index, cells in enumerate(columns):
            style = "bold yellow" if index == selected else "cyan"
            text.append(cells[row] * bar, style=style)
            text.append(" ")
        text.append("\n")
    text.append(" " * (gutter - 2) + "0└", style="dim")
    for index, b in enumerate(report.buckets):
        if index == selected:
            text.append("━" * bar, style="bold yellow")
            text.append("─", style="dim")
        else:
            text.append(("┈" if report.is_future(b) else "─") * column, style="dim")
    for line in x_labels(report, column, plot_width):
        text.append("\n" + " " * gutter + line, style="dim")
    return text


# The screen


def format_day(day: date) -> str:
    return f"{day:%a %d %b %Y}"


def format_money(amount: float) -> str:
    return f"{amount:,.2f}".removesuffix(".00")


def tabs(ranges: list[Range], current: int, width: int) -> Text:
    """The ranges on one line, the current one highlighted; short if needed."""

    def line(short: bool) -> Text:
        text = Text()
        for index, r in enumerate(ranges):
            if index:
                text.append(" ")
            style = "bold reverse" if index == current else "dim"
            text.append(f" {r.short if short else r.label} ", style=style)
        return text

    full = line(short=False)
    return full if full.cell_len <= width else line(short=True)


def summary(report: Report) -> list[str]:
    r = report.range
    unit = report.unit
    lines = [
        f"[bold]{format_duration(report.total)}[/bold] tracked in "
        f"{report.sessions} session{'s' if report.sessions != 1 else ''}"
        + (" [green](one running)[/green]" if report.running else ""),
    ]
    days = report.days_so_far
    left = r.days - days
    if report.days_worked:
        average = report.total / report.days_worked
        lines.append(
            f"{report.days_worked} of {days} day{'s' if days != 1 else ''} "
            f"worked · {format_duration(average)} per day worked"
            + (f" · {left} day{'s' if left != 1 else ''} left" if left else "")
        )
        busiest = max(report.buckets, key=lambda b: b.time)
        lines.append(
            f"Busiest {unit}: {bucket_name(busiest.start, unit)} · "
            f"{format_duration(busiest.time)}"
        )
    if report.project.rate:
        earned = report.total.total_seconds() / 3600 * report.project.rate
        lines.append(f"Earned: {format_money(earned)} at {report.project.rate}/h")
    return lines


def selection(report: Report, selected: int) -> str:
    """The selected bar: its time, and whether Enter zooms into it."""

    bucket = report.buckets[selected]
    name = bucket_name(bucket.start, report.unit)
    zoom = f" · Enter: its {SMALLER[report.unit]}s" if report.unit in SMALLER else ""
    return (
        f"[bold yellow]▌[/bold yellow] [bold]{name[0].upper()}{name[1:]}[/bold] "
        f"· {format_duration(bucket.time)}[dim]{zoom}[/dim]"
    )


def hints(report: Report, zoomed: bool) -> list[tuple[str, str]]:
    """The footer's keys: Enter while a bar has smaller ones, Esc when zoomed."""

    zoom = (
        ([("⏎/Esc", "zoom in/out")] if zoomed else [("⏎", "zoom")])
        if report.unit in SMALLER
        else [("Esc", "zoom out")]
        if zoomed
        else []
    )
    return [
        ("h/l", "bar"),
        *zoom,
        ("Tab", "range"),
        ("y", "copy project id"),
        ("?", "help"),
        ("q", "quit"),
    ]


def title(report: Report) -> str:
    """ "Report · website", with the project's dates."""

    dates = format_dates(report.project)
    return f"Report · {report.project.name}" + (f" · {dates}" if dates else "")


def body(
    report: Report,
    ranges: list[Range],
    current: int,
    width: int,
    height: int,
    selected: int | None = None,
) -> list[RenderableType]:
    """
    The report under its title: range tabs, the range, summary, the selected
    bar (if any), chart.
    """

    r = report.range
    return [
        tabs(ranges, current, width),
        "",
        (
            f"[bold]{r.label}[/bold] [dim]· {format_day(r.start)} → "
            f"{format_day(r.end)} · one bar per {report.unit}[/dim]"
        ),
        "",
        *summary(report),
        *([selection(report, selected)] if selected is not None else []),
        "",
        chart(report, width, height, selected),
    ]


def screen(
    report: Report,
    ranges: list[Range],
    current: int,
    width: int,
    height: int,
) -> Group:
    """The report as printed: its title, then `body`."""

    dates = format_dates(report.project)
    heading = f"[bold]Report · [green]{escape(report.project.name)}[/green][/bold]"
    if dates:
        heading += f" [dim]· {dates}[/dim]"
    return Group(heading, "", *body(report, ranges, current, width, height))


# Lines around the printed chart: title, tabs, range, summary (up to 4), labels.
OTHER_LINES = 18


def chart_height(console: Console) -> int:
    return max(4, min(12, console.height - OTHER_LINES - dev_bar.lines()))


def render(
    project: Project,
    sessions: list[Session],
    ranges: list[Range],
    current: int,
    console: Console,
    now: datetime,
) -> Group:
    """The report to print, as wide as the console."""

    # The y axis takes a few columns: keep them out of the bars' width.
    width = console.width
    report = build_report(project, sessions, ranges[current], width - 8, now)
    height = chart_height(console)
    return screen(report, ranges, current, width, height)


def first_day(project: Project, sessions: list[Session], today: date) -> date:
    """The project's start or its first session, whichever comes first."""

    days = [sessions[0].start.astimezone().date()] if sessions else []
    if project.start:
        days.append(project.start)
    return min(days, default=today)


def latest_day(project: Project, sessions: list[Session], now: datetime) -> date | None:
    """The project's last session (today if running), start or end, the latest."""

    days = [(s.end or now).astimezone().date() for s in sessions]
    days += [day for day in (project.start, project.end) if day]
    return max(days, default=None)


def project_ranges(
    project: Project, sessions: list[Session], now: datetime
) -> list[Range]:
    today = now.astimezone().date()
    return report_ranges(
        first_day(project, sessions, today),
        today,
        project.end,
        latest_day(project, sessions, now),
    )


def asked_range(
    db: DBSession,
    project: Project,
    since: str | None,
    until: str | None,
    now: datetime | None = None,
) -> Range | None:
    """
    The days asked with --from/--to, if any: from the project's first day
    and up to today by default.
    """

    if since is None and until is None:
        return None
    today = (now or datetime.now(UTC)).astimezone().date()
    try:
        start = (
            parse_date(since, today)
            if since
            else first_day(project, load_sessions(db, project), today)
        )
    except ValueError as e:
        raise ValueError(f"--from: {e}") from None
    try:
        end = parse_date(until, today) if until else today
    except ValueError as e:
        raise ValueError(f"--to: {e}") from None
    if end < start:
        raise ValueError(f"--to ({end}) comes before --from ({start}).")
    return Range("custom", "Custom", "Custom", start, end)


def report_json(
    db: DBSession,
    project: Project,
    key: str | None = None,
    now: datetime | None = None,
    custom: Range | None = None,
) -> dict[str, Any]:
    """
    The report for `--json`: the range `key` (since the start by default) or
    the `custom` days, the time tracked on each of its days, and the totals.
    Unlike the screen, every range can be asked for, and the days are never
    grouped.
    """

    now = now or datetime.now(UTC)
    today = now.astimezone().date()
    sessions = load_sessions(db, project)
    ranges = all_ranges(first_day(project, sessions, today), today, project.end)
    r = custom or next((r for r in ranges if r.key == key), ranges[0])
    # As wide as needed for a bar per day.
    report = build_report(project, sessions, replace(r, unit="day"), width=0, now=now)
    return {
        "project": {"id": project.id, "name": project.name},
        "range": {"key": r.key, "label": r.label, "start": r.start, "end": r.end},
        "ranges": [r.key for r in project_ranges(project, sessions, now)],
        "days": [
            {"date": bucket.start, "tracked_seconds": seconds(bucket.time)}
            for bucket in report.buckets
        ],
        "tracked_seconds": seconds(report.total),
        "sessions": report.sessions,
        "days_worked": report.days_worked,
        "running": report.running,
        "earned": (
            round(report.total.total_seconds() / 3600 * project.rate, 2)
            if project.rate
            else None
        ),
    }


def start_index(ranges: list[Range], key: str | None) -> int:
    """The range with `key`, if shown; else the first one."""

    keys = [r.key for r in ranges]
    return keys.index(key) if key in keys else 0


def shown_ranges(
    project: Project, sessions: list[Session], now: datetime, custom: Range | None
) -> list[Range]:
    """The ranges in the tabs: the `custom` days first, if any."""

    return [*([custom] if custom else []), *project_ranges(project, sessions, now)]


def print_report(
    db: DBSession,
    project: Project,
    key: str | None = None,
    now: datetime | None = None,
    custom: Range | None = None,
) -> None:
    """Print the report once, without waiting for keys."""

    now = now or datetime.now(UTC)
    sessions = load_sessions(db, project)
    ranges = shown_ranges(project, sessions, now, custom)
    console = get_console()
    console.print(
        render(
            project,
            sessions,
            ranges,
            start_index(ranges, key),
            console,
            now,
        )
    )


SHORTCUTS: list[browser.Shortcut] = [
    ("l  →", ("l", "\x1b[C"), "right", "Next bar"),
    ("h  ←", ("h", "\x1b[D"), "left", "Previous bar"),
    ("g", ("g",), "first", "First bar"),
    ("G", ("G",), "last", "Last bar"),
    ("Enter", ("\r", "\n"), "zoom", "Zoom into the bar: its months, weeks or days"),
    ("Esc  ⌫", (ESC, "\x7f", "\x08"), "back", "Zoom out (quit when not zoomed)"),
    ("Tab  ]", ("\t", "]"), "next", "Next range"),
    ("S-Tab  [", ("\x1b[Z", "["), "previous", "Previous range"),
    ("1-9", tuple("123456789"), "jump", "Jump to a range"),
    ("r", ("r",), "refresh", "Refresh"),
    ("y", ("y",), "copy", "Copy the project's id"),
    ("?", ("?",), "help", "Show these shortcuts"),
    ("q", ("q",), "quit", "Quit"),
]


@dataclass
class Place:
    """Where the report is: a range tab, the bars zoomed into, the bar selected."""

    current: int
    selected: date
    # The ranges zoomed into, outermost first, each with the day selected
    # before zooming (selected again when zooming out).
    zooms: list[tuple[Range, date]]

    def range(self, ranges: list[Range]) -> Range:
        return self.zooms[-1][0] if self.zooms else ranges[self.current]


def first_selected(r: Range, today: date) -> date:
    """Today's bar if the range has it, else its first."""

    return today if r.start <= today <= r.end else r.start


def frame(
    console: Console,
    size: tuple[int, int],
    report: Report,
    ranges: list[Range],
    current: int,
    selected: int,
    zoomed: bool = False,
    message: str = "",
) -> tui.Frame:
    """The report full screen: the chart takes the height left."""

    width, height = size
    inner_width, inner_height = tui.body_size(width, height)
    options = console.options.update(width=inner_width)
    smallest = 2

    def lines(chart_lines: int) -> Group:
        return Group(*body(report, ranges, current, inner_width, chart_lines, selected))

    others = len(console.render_lines(lines(smallest), options))
    chart_lines = max(smallest, smallest + inner_height - others)
    return tui.page(
        console,
        width,
        height,
        title=title(report),
        body=lines(chart_lines),
        footer=Text.from_markup(f" {message}")
        if message
        else tui.hints(hints(report, zoomed)),
    )


def show(
    db: DBSession,
    project: Project,
    key: str | None = None,
    read_key: Callable[[], str] | None = None,
    now: Callable[[], datetime] | None = None,
    custom: Range | None = None,
) -> None:
    """Show the report full screen until the user quits."""

    read_key = read_key or browser.getchar
    now = now or (lambda: datetime.now(UTC))
    key_actions = {code: action for _, codes, action, _ in SHORTCUTS for code in codes}

    def keys() -> Iterator[str]:
        while True:
            yield from tui.split_keys(read_key()) or [browser.RESIZE]

    pressed = keys()
    sessions = load_sessions(db, project)
    moment = now()
    ranges = shown_ranges(project, sessions, moment, custom)

    def today() -> date:
        return moment.astimezone().date()

    def on_tab(index: int) -> Place:
        return Place(index, first_selected(ranges[index], today()), [])

    place = on_tab(start_index(ranges, key))

    with tui.open_screen() as view:
        console = view.console
        message = ""
        while True:
            # The y axis takes a few columns: keep them out of the bars' width.
            inner_width, _ = tui.body_size(*view.size())
            report = build_report(
                project, sessions, place.range(ranges), inner_width - 8, moment
            )
            selected = report.index_of(place.selected)
            page = frame(
                console,
                view.size(),
                report,
                ranges,
                place.current,
                selected,
                bool(place.zooms),
                message,
            )
            view.draw(page)
            message = ""

            starts = [bucket.start for bucket in report.buckets]
            # Ignore keys that do nothing here, without redrawing.
            last_bar = len(starts) - 1
            for pressed_key in pressed:
                if pressed_key == browser.RESIZE:
                    action = "redraw"
                    break
                action = key_actions.get(pressed_key)
                if action in ("right", "last") and selected == last_bar:
                    continue
                if action in ("left", "first") and selected == 0:
                    continue
                if action == "zoom" and report.unit not in SMALLER:
                    continue
                if action == "next" and place.current == len(ranges) - 1:
                    continue
                if action == "previous" and place.current == 0:
                    continue
                if action == "jump" and int(pressed_key) > len(ranges):
                    continue
                if action is not None:
                    break

            if action == "quit" or (action == "back" and not place.zooms):
                return
            if action == "copy":
                message = clipboard.copied(str(project.id), console, what="project")
            elif action == "help":
                view.draw(tui.overlay(console, page, browser.help_panel(SHORTCUTS)))
                next(pressed)
            elif action == "right":
                place.selected = starts[selected + 1]
            elif action == "left":
                place.selected = starts[selected - 1]
            elif action == "first":
                place.selected = starts[0]
            elif action == "last":
                place.selected = starts[last_bar]
            elif action == "zoom":
                zoomed = zoom_range(report.range, report.buckets[selected], report.unit)
                if zoomed is not None:
                    place.zooms.append((zoomed, place.selected))
                    place.selected = first_selected(zoomed, today())
            elif action == "back":
                _, place.selected = place.zooms.pop()
            elif action == "next":
                place = on_tab(place.current + 1)
            elif action == "previous":
                place = on_tab(place.current - 1)
            elif action == "jump":
                place = on_tab(int(pressed_key) - 1)
            elif action == "refresh":
                selected_key = ranges[place.current].key
                db.expire_all()
                sessions = load_sessions(db, project)
                moment = now()
                ranges = shown_ranges(project, sessions, moment, custom)
                current = start_index(ranges, selected_key)
                # Zoomed days stay as they were; a range gone starts over.
                if ranges[current].key != selected_key:
                    place = on_tab(current)
                else:
                    place.current = current
