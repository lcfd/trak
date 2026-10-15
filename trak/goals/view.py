"""
`trak goals show` (or `trak goals ID`): a Goal, full screen, in two panes
(`views.py`): its details and progress, and the sessions that count towards
it. With --plain, without a terminal or with --json, it prints the details
and exits.
"""

from datetime import timedelta
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, output, views
from trak.goals.commands import IdArgument, ask_edits, get_or_pick
from trak.goals.display import (
    days_text,
    describe_goal,
    format_day,
    goal_json,
    pace_text,
    progress_bar,
    to_go_text,
    tracked_text,
)
from trak.goals.models import Goal
from trak.goals.services import goal_progress, update_goal
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.editing import row_name
from trak.sessions.services import list_sessions, local_midnight

# The progress bar in the details, in cells.
BAR = 36


def goal_rows(db: DBSession, goal: Goal) -> list[tuple[str, str]]:
    """Every field of the Goal and how far along it is, as Rich markup."""

    progress = goal_progress(db, goal)
    return [
        ("Project", f"[green]{escape(row_name(db, Project, goal.project_fk))}[/green]"),
        ("Name", entities.or_dash(goal.name)),
        ("Hours", f"{goal.hours}h"),
        ("From", format_day(goal.start)),
        ("Deadline", format_day(goal.deadline)),
        ("Tracked", tracked_text(progress)),
        ("Status", to_go_text(progress)),
        ("Days", days_text(progress)),
    ]


class GoalView(views.DetailView):
    model = Goal
    title = "Goal"
    noun = "goal"
    listing = "sessions counted"

    def fill(self, db: DBSession, goal: Goal) -> None:
        progress = goal_progress(db, goal, now=self.now())
        self.headline = describe_goal(db, goal)
        self.rows = goal_rows(db, goal)
        self.extra = [progress_bar(progress, BAR).markup]
        pace = pace_text(progress)
        if pace:
            self.extra.append(pace)

        sessions, total = list_sessions(
            db,
            project_fk=goal.project_fk,
            start_from=local_midnight(goal.start),
            start_until=local_midnight(goal.deadline + timedelta(days=1)),
            limit=views.SESSIONS,
        )
        self.list.title = f"Sessions counted ({total})"
        self.list.empty = (
            "No session counts yet.\n\n"
            f"[dim]Sessions on the project from {goal.start} to {goal.deadline}"
            " count.[/dim]"
        )
        self.list.load(db, sessions, current=None)

    def ask_edits(self, db: DBSession, prompter: Any, row: Any) -> dict[str, Any]:
        return ask_edits(db, prompter, row)

    def update(self, db: DBSession, row: Any, **changes: Any) -> Any:
        return update_goal(db, row, **changes)


def show_command(
    ctx: typer.Context,
    goal_id: IdArgument = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain", help="Print the goal and exit, instead of the full screen."
        ),
    ] = False,
) -> None:
    """
    Show a goal: its project, hours, days, how far along it is and the
    sessions that count towards it.
    """

    engine = ctx.obj["DB_ENGINE"]
    with DBSession(engine) as db:
        goal = get_or_pick(db, goal_id, "show")
        output.emit(goal_json(db, goal))
        if plain or not commands.is_interactive():
            entities.print_details(
                title=f"Goal #{goal.id}",
                rows=goal_rows(db, goal),
                hint=f'Edit it with "trak goals edit {goal.id}".',
            )
            return
        assert goal.id is not None
        view = GoalView(engine, goal.id)
    views.run(view)
