"""`trak goals list`: browse goals, nearest deadline first."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table
from sqlmodel import Session as DBSession

from trak import browser, entities
from trak.goals.display import days_text, to_go_text, tracked_text
from trak.goals.models import Goal
from trak.goals.services import goal_progress, list_goals
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.guided import Prompter
from trak.sessions.listing import ask_project


@dataclass
class GoalFilters:
    project: Project | None = None
    past: bool = False
    page: int = 1
    per_page: int = 20

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


def build_table(db: DBSession, goals: list[Goal], cursor: int | None = None) -> Table:
    """The goals table; the row at `cursor`, if any, is highlighted."""

    table = Table(header_style="bold", show_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Project", style="green")
    table.add_column("Name")
    table.add_column("Tracked", justify="right")
    table.add_column("To go", justify="right")
    table.add_column("Deadline")
    table.add_column("Days")

    now = datetime.now(UTC)
    for index, goal in enumerate(goals):
        project = db.get(Project, goal.project_fk)
        progress = goal_progress(db, goal, now=now)
        table.add_row(
            str(goal.id),
            escape(project.name) if project else "",
            escape(goal.name),
            tracked_text(progress),
            to_go_text(progress, suffix=""),
            f"{goal.deadline}",
            days_text(progress),
            style="reverse" if index == cursor else None,
        )
    return table


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("p", ("p",), "project", "Filter by project"),
    ("a", ("a",), "past", "Show or hide past goals"),
]
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def goal_listing(db: DBSession) -> browser.Listing[Goal, GoalFilters]:
    return browser.Listing(
        noun="goal",
        query=lambda filters: query(db, filters),
        table=lambda goals, cursor: build_table(db, goals, cursor),
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
) -> Goal | None:
    """Browse the goals until the user quits (None), or pick one."""

    return browser.browse(
        goal_listing(db),
        prompter,
        filters,
        read_key=read_key,
        pick=pick,
        title=title,
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
        int, typer.Option("--per-page", min=1, max=500, help="Goals per page.")
    ] = 20,
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

        filters = GoalFilters(project=project, past=past, page=page, per_page=per_page)

        if plain or not commands.is_interactive():
            browser.print_page(goal_listing(db), filters)
            return

        entities.run_browser(lambda prompter: browse(db, prompter, filters))
