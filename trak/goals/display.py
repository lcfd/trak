"""How Goals look: their progress, days left, and the reminder above `trak`."""

from datetime import UTC, date, datetime, timedelta

from rich.console import Console, Group
from rich.markup import escape
from rich.padding import Padding
from rich.progress_bar import ProgressBar
from rich.table import Table
from sqlmodel import Session as DBSession

from trak.goals.models import Goal
from trak.goals.services import Progress, goal_progress, upcoming_goals
from trak.projects.models import Project
from trak.sessions.display import format_duration


def format_day(day: date) -> str:
    return f"{day:%a %d %b %Y}"


def format_days_left(days: int) -> str:
    if days < 0:
        return f"ended {-days} day{'s' if days < -1 else ''} ago"
    if days == 0:
        return "due today"
    return f"{days} day{'s' if days > 1 else ''} left"


def describe_goal(db: DBSession, goal: Goal) -> str:
    """Plain text: "project · name", or just the project."""

    project = db.get(Project, goal.project_fk)
    parts = [project.name if project else f"Project #{goal.project_fk}", goal.name]
    return " · ".join(part for part in parts if part)


def goal_label(db: DBSession, goal: Goal) -> str:
    return f"[green]{escape(describe_goal(db, goal))}[/green]"


def tracked_text(progress: Progress) -> str:
    """ "12h 30m of 40h"."""

    hours = int(progress.budget.total_seconds()) // 3600
    return f"{format_duration(progress.tracked)} of {hours}h"


# A working day, to turn the time to go into days of work.
HOURS_PER_DAY = 8


def time_to_go(progress: Progress) -> timedelta:
    # Count whole tracked minutes, as `tracked_text` shows them: the two add up.
    tracked = timedelta(minutes=int(progress.tracked.total_seconds()) // 60)
    return progress.budget - tracked


def to_go_text(progress: Progress, suffix: str = " to go") -> str:
    if progress.reached:
        return "[bold green]reached ✓[/bold green]"
    return f"{format_duration(time_to_go(progress))}{suffix}"


def work_days(progress: Progress) -> float:
    """The time to go in working days of HOURS_PER_DAY."""

    return time_to_go(progress) / timedelta(hours=HOURS_PER_DAY)


def daily_pace(progress: Progress) -> timedelta:
    """The time to track each day, today and the deadline included, to make it."""

    return time_to_go(progress) / (progress.days_left + 1)


def pace_text(progress: Progress) -> str | None:
    """
    How the time to go fits the days left: "1.9 workdays needed, ~58m a day".
    Red when it takes more than a workday a day. None once reached or past.
    """

    if progress.reached or progress.days_left < 0:
        return None
    days = f"{work_days(progress):.1f}".removesuffix(".0")
    pace = daily_pace(progress)
    minutes = int(pace.total_seconds() // 60)
    per_day = f"{minutes}m" if minutes < 60 else format_duration(pace)
    text = f"{days} workday{'' if days == '1' else 's'} needed, ~{per_day} a day"
    if pace > timedelta(hours=HOURS_PER_DAY):
        return f"[bold red]{text}[/bold red]"
    return f"[dim]{text}[/dim]"


def days_text(progress: Progress) -> str:
    text = format_days_left(progress.days_left)
    if progress.reached or progress.days_left > 7:
        return text
    if progress.days_left < 0:
        return f"[dim]{text}[/dim]"
    # A week or less left and still not reached.
    return f"[bold yellow]{text}[/bold yellow]"


def progress_bar(progress: Progress, width: int = 20) -> ProgressBar:
    return ProgressBar(
        total=1,
        completed=min(progress.ratio, 1),
        width=width,
        complete_style="green" if progress.reached else "cyan",
        finished_style="green",
    )


def goal_block(db: DBSession, goal: Goal, now: datetime) -> Group:
    """
    One Goal of the reminder, on three lines (four until it's reached):

        website · Launch
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  31%
        12h 30m of 40h tracked · 27h 30m to go · 16 days left, by Fri 30 Oct
        3.4 workdays needed, ~1h 37m a day
    """

    progress = goal_progress(db, goal, now=now)

    bar = Table.grid(padding=(0, 2))
    bar.add_column()
    bar.add_column(justify="right", style="bold")
    bar.add_row(progress_bar(progress, width=30), f"{min(progress.ratio, 1):.0%}")

    parts = [
        f"[bold]{tracked_text(progress)}[/bold] tracked",
        to_go_text(progress),
        f"{days_text(progress)}, by {goal.deadline:%a %d %b}",
    ]
    details = " [dim]·[/dim] ".join(parts)
    pace = pace_text(progress)
    return Group(
        f"[bold green]{escape(describe_goal(db, goal))}[/bold green]",
        bar,
        details,
        *([pace] if pace else []),
    )


def print_reminder(
    console: Console, db: DBSession, now: datetime | None = None
) -> None:
    """The upcoming Goals, nearest deadline first; nothing if there are none."""

    now = now or datetime.now(UTC)
    goals = upcoming_goals(db, on=now.astimezone().date())
    if not goals:
        return

    console.print(f"[bold]🎯 Goals[/bold] [dim]({len(goals)})[/dim]\n")
    for goal in goals:
        console.print(Padding(goal_block(db, goal, now), (0, 0, 1, 2)))
