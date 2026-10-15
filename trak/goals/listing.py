"""`trak goals list`: browse goals, nearest deadline first."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import browser, entities, tables, tui
from trak.goals.display import days_text, goal_json, to_go_text, tracked_text
from trak.goals.models import Goal
from trak.goals.services import Progress, goal_progress, list_goals
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.guided import Prompter
from trak.sessions.listing import ask_project


@dataclass
class GoalFilters:
    project: Project | None = None
    past: bool = False
    page: int = 1
    per_page: int = browser.PER_PAGE

    @property
    def active(self) -> bool:
        return bool(self.project or self.past)

    def describe(self) -> str:
        parts = []
        if self.project:
            parts.append(f"project: {escape(self.project.name)}")
        if self.past:
            parts.append("with past")
        return " · ".join(parts) or "none"


def query(db: DBSession, filters: GoalFilters) -> tuple[list[Goal], int]:
    return list_goals(
        db,
        project_fk=filters.project.id if filters.project else None,
        past=filters.past,
        limit=filters.per_page,
        offset=(filters.page - 1) * filters.per_page,
    )


def days_short(progress: Progress) -> str:
    """ "40d", "today", "ended": the days left, colored like `days_text`."""

    days = progress.days_left
    if days < 0:
        return "[dim]ended[/dim]"
    text = "today" if days == 0 else f"{days}d"
    if not progress.reached and days <= 7:
        return f"[bold yellow]{text}[/bold yellow]"
    return text


def goal_cells(db: DBSession, goal: Goal) -> tables.Cells:
    """Every cell a goals table can show, as markup."""

    now = datetime.now(UTC)
    project = db.get(Project, goal.project_fk)
    progress = goal_progress(db, goal, now=now)
    project_name = escape(project.name) if project else ""
    name = escape(goal.name)
    percent = f"{min(progress.ratio, 1):.0%}"
    return {
        "id": str(goal.id),
        "project": project_name,
        "name": name,
        "goal": f"[green]{project_name}[/green]"
        + (f" [dim]·[/dim] {name}" if name else ""),
        "tracked": tracked_text(progress),
        "to_go": to_go_text(progress, suffix=""),
        "deadline": f"{goal.deadline}",
        "deadline_short": tables.short_day(goal.deadline, now.astimezone().date()),
        "days": days_text(progress),
        "days_short": days_short(progress),
        "done": f"[green]{percent}[/green]" if progress.reached else percent,
    }


# "project · name" reads badly cut short: rather drop a column.
GOAL = tables.col("goal", flex=True, least=24)
# Widest first; see `tables.py`.
LAYOUTS: list[tables.Layout] = [
    [
        tables.ID,
        tables.col("project", style="green"),
        tables.col("name", flex=True),
        tables.col("tracked", right=True),
        tables.col("to_go", "To go", right=True),
        tables.col("deadline"),
        tables.col("days"),
    ],
    [
        tables.ID,
        GOAL,
        tables.col("tracked", right=True),
        tables.col("deadline_short", "Deadline"),
        tables.col("days"),
    ],
    [
        tables.ID,
        GOAL,
        tables.col("done", right=True),
        tables.col("days_short", "Left", right=True),
    ],
    [tables.ID, GOAL, tables.col("done", right=True)],
]


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("p", ("p",), "project", "Filter by project"),
    ("a", ("a",), "past", "Show or hide past goals"),
]
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def show_goal(db: DBSession, goal: Goal, screen: tui.Screen) -> None:
    from trak import views
    from trak.goals.view import GoalView

    views.show_in(db, GoalView, goal, screen)


def edit_goal(db: DBSession, goal: Goal, prompter: Prompter) -> str:
    from trak.goals.commands import ask_edits
    from trak.goals.display import goal_label
    from trak.goals.services import update_goal

    return entities.edit_in_place(
        db,
        goal,
        prompter,
        ask=ask_edits,
        update=update_goal,
        noun="goal",
        label=lambda g: goal_label(db, g),
    )


def goal_listing(db: DBSession) -> browser.Listing[Goal, GoalFilters]:
    return browser.Listing(
        show=lambda goal, screen: show_goal(db, goal, screen),
        edit=lambda goal, prompter: edit_goal(db, goal, prompter),
        noun="goal",
        query=lambda filters: query(db, filters),
        cells=lambda goal: goal_cells(db, goal),
        layouts=LAYOUTS,
        to_json=lambda goal: goal_json(db, goal),
        filter_shortcuts=FILTER_SHORTCUTS,
        ask_filter=lambda prompter, filters, action: ask_project(db, prompter, filters),  # type: ignore[arg-type]
        clear=lambda filters: GoalFilters(per_page=filters.per_page),
        toggles={
            "past": lambda filters: replace(filters, past=not filters.past, page=1)
        },
    )


def browse(
    db: DBSession,
    prompter: Prompter,
    filters: GoalFilters,
    read_key: Callable[[], str] | None = None,
    pick: bool = False,
    title: str = "Goals",
    fit: bool = True,
) -> Goal | None:
    """Browse the goals until the user quits (None), or pick one."""

    return browser.browse(
        goal_listing(db),
        prompter,
        filters,
        read_key=read_key,
        pick=pick,
        title=title,
        fit=fit,
    )


def list_command(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Only the goals of this project."),
    ] = None,
    past: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include goals whose deadline has passed."),
    ] = False,
    page: Annotated[int, typer.Option("--page", min=1, help="The page to show.")] = 1,
    per_page: Annotated[
        int | None,
        typer.Option(
            "--per-page",
            min=1,
            max=500,
            help="Goals per page. Default: what fits the terminal; 20 when printed.",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print one page and exit, instead of browsing interactively.",
        ),
    ] = False,
) -> None:
    """
    Browse goals, nearest deadline first. The options set the starting filters.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = commands.find_project(db, project_name, archived=True)
            if project is None:
                raise typer.Exit(1)

        filters = GoalFilters(
            project=project, past=past, page=page, per_page=per_page or browser.PER_PAGE
        )

        if plain or not commands.is_interactive():
            browser.print_page(goal_listing(db), filters)
            return

        entities.run_browser(
            lambda prompter: browse(db, prompter, filters, fit=per_page is None)
        )
