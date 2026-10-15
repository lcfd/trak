"""
`trak projects show` (or `trak projects ID`): a Project, full screen, in two
panes (`views.py`): its details and goals, and its sessions. `R` opens its
report. With --plain, without a terminal or with --json, it prints the
details and exits.
"""

from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession
from sqlmodel import col, select

from trak import entities, output, tui, views
from trak.dates import today
from trak.goals.display import days_text, format_day, progress_bar
from trak.goals.models import Goal
from trak.goals.services import goal_progress
from trak.labels.links import label_details
from trak.projects import report
from trak.projects.commands import (
    IdArgument,
    ask_edits,
    customer_of,
    end_text,
    get_or_pick,
    project_label,
)
from trak.projects.listing import format_rate, project_json
from trak.projects.models import Project
from trak.projects.services import update_project
from trak.sessions import commands
from trak.sessions.display import describe_session, format_duration
from trak.sessions.editing import format_time
from trak.sessions.services import list_sessions, session_totals

# The progress bars of the goals, in cells.
BAR = 16


def project_rows(db: DBSession, project: Project) -> list[tuple[str, str]]:
    """Every field of the Project and the time tracked on it, as Rich markup."""

    totals = session_totals(db, project_fk=project.id)
    return [
        ("Name", project_label(project)),
        ("Customer", entities.or_dash(customer_of(db, project))),
        *label_details(db, project),
        ("Rate", entities.or_dash(format_rate(project.rate))),
        ("Description", entities.or_dash(project.description)),
        ("Start", entities.or_dash(project.start and format_day(project.start))),
        ("End", end_text(project) or entities.or_dash(None)),
        ("Status", "archived" if project.archived else "active"),
        ("Sessions", str(totals.sessions)),
        ("Time", format_duration(totals.time)),
        ("Last session", entities.or_dash(totals.last and format_time(totals.last))),
    ]


class ProjectView(views.DetailView):
    model = Project
    title = "Project"
    noun = "project"
    listing = "sessions"

    def fill(self, db: DBSession, project: Project) -> None:
        self.headline = project.name
        self.rows = project_rows(db, project)[1:]  # The name is the headline.
        self.extra = self.goal_lines(db, project)

        sessions, total = list_sessions(db, project_fk=project.id, limit=views.SESSIONS)
        self.list.title = f"Sessions ({total})"
        self.list.empty = (
            "No sessions yet.\n\n"
            f'[dim]Start one with "trak start {escape(project.name)}".[/dim]'
        )
        # The project is in the title: say the rest (the session's own customer).
        self.list.load(
            db,
            sessions,
            describe=lambda s: (
                s.name or "(no name)"
                if s.customer_fk is None
                else describe_session(db, s)
            ),
            current=None,
        )

    def goal_lines(self, db: DBSession, project: Project) -> list[str]:
        goals = list(
            db.exec(
                select(Goal)
                .where(Goal.project_fk == project.id)
                .order_by(col(Goal.deadline))
            )
        )
        upcoming = [g for g in goals if g.deadline >= today()]
        lines = ["[bold]Goals[/bold]"]
        if not goals:
            return [*lines, "[dim]None yet: set one with trak goals create.[/dim]"]
        for goal in upcoming:
            progress = goal_progress(db, goal, now=self.now())
            name = escape(goal.name or f"{goal.hours}h")
            lines.append(
                f"{progress_bar(progress, BAR).markup}  {name} "
                f"[dim]·[/dim] {days_text(progress)}"
            )
        past = len(goals) - len(upcoming)
        if past:
            reached = sum(
                goal_progress(db, g).reached for g in goals if g not in upcoming
            )
            lines.append(f"[dim]{past} past, {reached} reached[/dim]")
        return lines

    def ask_edits(self, db: DBSession, prompter: Any, row: Any) -> dict[str, Any]:
        return ask_edits(db, prompter, row)

    def update(self, db: DBSession, row: Any, **changes: Any) -> Any:
        return update_project(db, row, **changes)

    def key(self, screen: tui.Screen, key: str) -> bool:
        if key != "R":
            return False
        with DBSession(self.engine) as db:
            project = db.get(Project, self.row_id)
            assert project is not None
            report.show(db, project, now=self.now)
        self.load()
        return True

    def extra_hints(self) -> list[tuple[str, str]]:
        return [("R", "report")]

    def extra_help(self) -> list[tuple[str, str]]:
        return [("R", "The project's report")]


def show_command(
    ctx: typer.Context,
    project_id: IdArgument = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain", help="Print the project and exit, instead of the full screen."
        ),
    ] = False,
) -> None:
    """
    Show a project: its fields, its goals, the time tracked on it and its
    sessions.
    """

    engine = ctx.obj["DB_ENGINE"]
    with DBSession(engine) as db:
        project = get_or_pick(db, project_id, "show")
        output.emit(project_json(db, project))
        if plain or not commands.is_interactive():
            entities.print_details(
                title=f"Project #{project.id}",
                rows=project_rows(db, project),
                hint=f'Edit it with "trak projects edit {project.id}".',
            )
            return
        assert project.id is not None
        view = ProjectView(engine, project.id)
    views.run(view)
