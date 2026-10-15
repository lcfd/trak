"""
`trak projects report`: the time tracked on a project, as a bar chart.

The report stays open: h/l switch the time range (since the start, last year,
... this week), `?` lists the shortcuts, q quits. Each bar is the time tracked
in a day; when the days don't fit the terminal, a bar is a week, a month or a
year instead.

Every day of the range has its bar, even an empty one, so skipped days show;
"this month" and "this week" run to their last day, with the days still to
come on a dotted axis.

"Since the start" runs from the project's start (or its first session, if
earlier) to its end, when that's still to come.

Sessions are split at local midnight, so a session from 23:00 to 01:00 counts
one hour on each day; running ones count until now.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any, Literal

from rich import get_console
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.text import Text
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import browser, dev_bar
from trak.output import seconds
from trak.projects.listing import format_dates
from trak.projects.models import Project
from trak.prompts import ESC, split_escape
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
    last_month_end = month_start - timedelta(days=1)
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
        Range(
            "last-month",
            "Last month",
            "Last mo",
            last_month_end.replace(day=1),
            last_month_end,
        ),
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


def report_ranges(first: date, today: date, last: date | None = None) -> list[Range]:
    """
    The ranges worth showing: not the ones ending before the first day
    (they'd be empty), nor the ones ending today that start on or before it
    (they'd be the same as "Since the start"). "This week" and "this month"
    end later, so they're always worth it: they show the days left.
    """

    since_start, *others = all_ranges(first, today, last)
    useful = [
        r
        for r in others
        if r.end >= first and not (r.end == today and r.start <= first)
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
    unit = choose_unit(r, width)
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


def chart(report: Report, width: int, height: int) -> Text:
    """The bars with a y axis on the left and the labels under them."""

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
        for cells in columns:
            text.append(cells[row] * bar, style="cyan")
            text.append(" ")
        text.append("\n")
    text.append(" " * (gutter - 2) + "0└", style="dim")
    for b in report.buckets:
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
        when = {
            "day": format_day(busiest.start),
            "week": f"week of {format_day(busiest.start)}",
            "month": f"{busiest.start:%B %Y}",
            "year": f"{busiest.start:%Y}",
        }[unit]
        lines.append(f"Busiest {unit}: {when} · {format_duration(busiest.time)}")
    if report.project.rate:
        earned = report.total.total_seconds() / 3600 * report.project.rate
        lines.append(f"Earned: {format_money(earned)} at {report.project.rate}/h")
    return lines


KEYS_HINT = (
    "[dim][bold]h[/bold]/[bold]l[/bold] range · [bold]?[/bold] shortcuts · "
    "[bold]q[/bold] quit[/dim]"
)


def screen(
    report: Report,
    ranges: list[Range],
    current: int,
    width: int,
    height: int,
    interactive: bool = True,
) -> Group:
    r = report.range
    dates = format_dates(report.project)
    parts: list[RenderableType] = [
        f"[bold]Report · [green]{escape(report.project.name)}[/green][/bold]"
        + (f" [dim]· {dates}[/dim]" if dates else ""),
        "",
        tabs(ranges, current, width),
        "",
        (
            f"[bold]{r.label}[/bold] [dim]· {format_day(r.start)} → "
            f"{format_day(r.end)} · one bar per {report.unit}[/dim]"
        ),
        "",
        *summary(report),
        "",
        chart(report, width, height),
    ]
    if interactive:
        parts += ["", KEYS_HINT]
    return Group(*parts)


# Lines around the chart: title, tabs, range, summary (up to 4), labels, footer.
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
    interactive: bool = True,
) -> Group:
    # The y axis takes a few columns: keep them out of the bars' width.
    width = console.width
    report = build_report(project, sessions, ranges[current], width - 8, now)
    height = chart_height(console)
    return screen(report, ranges, current, width, height, interactive)


def first_day(project: Project, sessions: list[Session], today: date) -> date:
    """The project's start or its first session, whichever comes first."""

    days = [sessions[0].start.astimezone().date()] if sessions else []
    if project.start:
        days.append(project.start)
    return min(days, default=today)


def project_ranges(
    project: Project, sessions: list[Session], now: datetime
) -> list[Range]:
    today = now.astimezone().date()
    return report_ranges(first_day(project, sessions, today), today, project.end)


def report_json(
    db: DBSession, project: Project, key: str | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """
    The report for `--json`: the range `key` (since the start by default),
    the time tracked on each of its days, and the totals. Unlike the screen,
    every range can be asked for, and the days are never grouped.
    """

    now = now or datetime.now(UTC)
    today = now.astimezone().date()
    sessions = load_sessions(db, project)
    ranges = all_ranges(first_day(project, sessions, today), today, project.end)
    r = next((r for r in ranges if r.key == key), ranges[0])
    # As wide as needed for a bar per day.
    report = build_report(project, sessions, r, width=r.days * MIN_COLUMN, now=now)
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


def print_report(
    db: DBSession, project: Project, key: str | None = None, now: datetime | None = None
) -> None:
    """Print the report once, without waiting for keys."""

    now = now or datetime.now(UTC)
    sessions = load_sessions(db, project)
    ranges = project_ranges(project, sessions, now)
    console = get_console()
    console.print(
        render(
            project,
            sessions,
            ranges,
            start_index(ranges, key),
            console,
            now,
            interactive=False,
        )
    )


SHORTCUTS: list[browser.Shortcut] = [
    ("l  →  Tab", ("l", "\x1b[C", "\t"), "next", "Next range"),
    ("h  ←", ("h", "\x1b[D", "\x1b[Z"), "previous", "Previous range"),
    ("g", ("g",), "first", "First range"),
    ("G", ("G",), "last", "Last range"),
    ("1-9", tuple("123456789"), "jump", "Jump to a range"),
    ("r", ("r",), "refresh", "Refresh"),
    ("?", ("?",), "help", "Show these shortcuts"),
    ("q  Esc", ("q", ESC), "quit", "Quit"),
]


def show(
    db: DBSession,
    project: Project,
    key: str | None = None,
    read_key: Callable[[], str] | None = None,
    now: Callable[[], datetime] | None = None,
) -> None:
    """Show the report until the user quits."""

    read_key = read_key or browser.getchar
    now = now or (lambda: datetime.now(UTC))
    console = get_console()
    key_actions = {code: action for _, codes, action, _ in SHORTCUTS for code in codes}

    def keys() -> Iterator[str]:
        while True:
            yield from split_escape(read_key())

    pressed = keys()
    sessions = load_sessions(db, project)
    moment = now()
    ranges = project_ranges(project, sessions, moment)
    current = start_index(ranges, key)

    console.show_cursor(False)
    try:
        while True:
            page = render(project, sessions, ranges, current, console, moment)
            dev_bar.clear(console)
            console.print(page)
            console.show_cursor(False)

            # Ignore keys that do nothing here, without redrawing.
            for pressed_key in pressed:
                action = key_actions.get(pressed_key)
                if action in ("next", "last") and current == len(ranges) - 1:
                    continue
                if action in ("previous", "first") and current == 0:
                    continue
                if action == "jump" and int(pressed_key) > len(ranges):
                    continue
                if action is not None:
                    break

            if action == "quit":
                return
            if action == "help":
                dev_bar.clear(console)
                browser.overlay(console, page, browser.help_panel(SHORTCUTS))
                next(pressed)
            elif action == "next":
                current += 1
            elif action == "previous":
                current -= 1
            elif action == "first":
                current = 0
            elif action == "last":
                current = len(ranges) - 1
            elif action == "jump":
                current = int(pressed_key) - 1
            elif action == "refresh":
                selected = ranges[current].key
                db.expire_all()
                sessions = load_sessions(db, project)
                moment = now()
                ranges = project_ranges(project, sessions, moment)
                current = start_index(ranges, selected)
    finally:
        console.show_cursor(True)
