"""How Goals look: their progress and days left (`show`, `list`, the home)."""

from datetime import date, datetime, timedelta
from typing import Any

from rich.markup import escape
from rich.text import Text
from sqlmodel import Session as DBSession

from trak import output
from trak.goals.models import Goal
from trak.goals.services import Progress, goal_progress
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


def goal_json(db: DBSession, goal: Goal, now: datetime | None = None) -> dict[str, Any]:
    """The Goal for `--json`: its fields, its project and its progress."""

    project = db.get(Project, goal.project_fk)
    progress = goal_progress(db, goal, now=now)
    return {
        **output.fields(goal),
        "project": project.name if project else None,
        "tracked_seconds": output.seconds(progress.tracked),
        "to_go_seconds": max(0, output.seconds(progress.budget - progress.tracked)),
        "reached": progress.reached,
        "days_left": progress.days_left,
    }


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


def progress_bar(progress: Progress, width: int) -> Text:
    """ "━━━━━━━━━━━━  31%": cyan as it goes, green once reached."""

    percent = f"{min(progress.ratio, 1):>4.0%}"
    bar_width = max(1, width - len(percent) - 1)
    done = round(bar_width * min(progress.ratio, 1))
    return Text.assemble(
        ("━" * done, "green" if progress.reached else "cyan"),
        ("━" * (bar_width - done), "bright_black"),
        " ",
        (percent, "bold"),
    )
