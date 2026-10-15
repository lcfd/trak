"""`trak goals create|show|edit`."""

from datetime import date, timedelta
from typing import Annotated, Any

import typer
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession

from trak import entities, forms
from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.goals import listing
from trak.goals.display import (
    days_text,
    format_day,
    goal_label,
    to_go_text,
    tracked_text,
)
from trak.goals.listing import GoalFilters
from trak.goals.models import Goal
from trak.goals.services import (
    check_goal,
    create_goal,
    goal_progress,
    today,
    update_goal,
)
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.sessions import commands
from trak.sessions.editing import row_name
from trak.sessions.guided import Prompter, input_validator

DATE_PLACEHOLDER = 'YYYY-MM-DD, "today", "tomorrow" or "+N" (in N days)'


def parse_hours(value: str) -> int:
    value = value.strip()
    if not value.isdigit() or int(value) == 0:
        raise ValueError("the hours must be a whole number, 1 or more")
    return int(value)


def parse_date(value: str, on: date | None = None) -> date:
    """
    A day typed by the user: "YYYY-MM-DD", "today", "tomorrow", or "+N" for
    N days from `on` (today).
    """

    value = value.strip().lower()
    on = on or today()
    if value == "today":
        return on
    if value == "tomorrow":
        return on + timedelta(days=1)
    if value.startswith("+") and value[1:].isdigit():
        return on + timedelta(days=int(value[1:]))
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"use {DATE_PLACEHOLDER}") from None


def parse_start(value: str) -> date:
    """Like `parse_date`, but empty means today."""

    return parse_date(value) if value.strip() else today()


hours_validator = input_validator(parse_hours)
start_validator = input_validator(parse_start)


def deadline_validator(start: date) -> Any:
    def parse(text: str) -> date:
        deadline = parse_date(text)
        if deadline < start:
            raise ValueError(f"the deadline can't come before the start ({start})")
        return deadline

    return input_validator(parse)


def pick_project(
    prompter: Prompter, projects: list[Project], default: int | None = None
) -> int:
    """Pick a project by id: a goal always has one."""

    options: list[Option[int]] = [
        {"name": p.name + (" (archived)" if p.archived else ""), "value": p.id}
        for p in projects
        if p.id is not None
    ]
    return prompter.ask("Project", options, allow_filtering=True, default=default)


# trak goals create


def ask_new_goal(
    db: DBSession, prompter: Prompter, project: Project | None = None
) -> dict[str, Any] | None:
    """Ask for every field of a new Goal. None means the user gave up."""

    fields: dict[str, Any] = {}
    if project is None:
        fields["project_fk"] = pick_project(prompter, get_projects(db))
    else:
        fields["project_fk"] = project.id
    fields["name"] = prompter.input("Name", placeholder="optional, e.g. Launch").strip()
    fields["hours"] = parse_hours(
        prompter.input("Hours", placeholder="e.g. 40", validator=hours_validator)
    )
    fields["start"] = parse_start(
        prompter.input(
            "From",
            placeholder=f"{DATE_PLACEHOLDER}; empty for today",
            validator=start_validator,
        )
    )
    fields["deadline"] = parse_date(
        prompter.input(
            "Deadline",
            placeholder=DATE_PLACEHOLDER,
            validator=deadline_validator(fields["start"]),
        )
    )

    if not prompter.confirm("Create this goal?"):
        return None
    return fields


def create_command(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Argument(
            metavar="PROJECT",
            help="The goal's project. Leave it empty to fill in every field.",
        ),
    ] = None,
    hours: Annotated[
        int | None,
        typer.Option("--hours", "-H", min=1, help="The hours to reach."),
    ] = None,
    deadline: Annotated[
        str | None,
        typer.Option(
            "--by", "-b", metavar="DATE", help=f"The deadline: {DATE_PLACEHOLDER}."
        ),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option(
            "--from",
            "-f",
            metavar="DATE",
            help="Count the time tracked from this day. Today if not given.",
        ),
    ] = None,
    name: Annotated[
        str, typer.Option("--name", "-n", help="A name for the goal.")
    ] = "",
) -> None:
    """
    Create a goal: hours to track on a project by a deadline. Without a
    project, asks for every field.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        if not get_projects(db):
            print_error(
                title="No projects yet",
                text=(
                    "A goal belongs to a project.\n\n"
                    'Create one with "trak projects create".'
                ),
            )
            raise typer.Exit(1)

        if project_name is None:
            entities.require_terminal("Creating a goal without a project")
            fields = commands.run_prompts(
                lambda prompter: ask_new_goal(db, prompter),
                cancelled="No goal was created.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No goal was created.")
                raise typer.Exit(1)
        else:
            project = commands.find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)
            if hours is None or deadline is None:
                print_error(
                    title="Can't create the goal",
                    text=(
                        "Give it the hours and the deadline, e.g.\n\n"
                        f'trak goals create "{project.name}" --hours 40 --by +30'
                    ),
                )
                raise typer.Exit(1)
            try:
                fields = {
                    "project_fk": project.id,
                    "name": name,
                    "hours": hours,
                    "deadline": parse_date(deadline),
                    "start": parse_date(start) if start is not None else None,
                }
            except ValueError as e:
                message = str(e)
                print_error(
                    title="Can't create the goal",
                    text=message[:1].upper() + message[1:],
                )
                raise typer.Exit(1)

        try:
            goal = create_goal(db, **fields)
        except ValueError as e:
            print_error(title="Can't create the goal", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="🎯 Create",
            text=(
                f"Goal #{goal.id} {goal_label(db, goal)} created: "
                f"{goal.hours}h by {format_day(goal.deadline)}.\n\n"
                'You\'ll see it on top of "trak".'
            ),
        )


# trak goals show / edit


IdArgument = Annotated[
    int | None,
    typer.Argument(
        metavar="ID", help="The goal. Leave it empty to pick one from the list."
    ),
]


def get_or_pick(db: DBSession, goal_id: int | None, verb: str) -> Goal:
    return entities.get_or_pick(
        db,
        Goal,
        goal_id,
        lambda prompter: listing.browse(
            db,
            prompter,
            GoalFilters(past=True),
            pick=True,
            title=f"Pick a goal to {verb}",
        ),
        noun="goal",
        command=f"trak goals {verb}",
        cancelled=f"No goal was {'shown' if verb == 'show' else 'edited'}.",
    )


def show_command(ctx: typer.Context, goal_id: IdArgument = None) -> None:
    """
    Show a goal: its project, hours, days and how far along it is.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        goal = get_or_pick(db, goal_id, "show")
        progress = goal_progress(db, goal)
        entities.print_details(
            title=f"Goal #{goal.id}",
            rows=[
                ("Project", f"[green]{row_name(db, Project, goal.project_fk)}[/green]"),
                ("Name", entities.or_dash(goal.name)),
                ("Hours", f"{goal.hours}h"),
                ("From", format_day(goal.start)),
                ("Deadline", format_day(goal.deadline)),
                ("Tracked", tracked_text(progress)),
                ("Status", to_go_text(progress)),
                ("Days", days_text(progress)),
            ],
            hint=f'Edit it with "trak goals edit {goal.id}".',
        )


def field_rows(db: DBSession, goal: Goal, changes: dict[str, Any]) -> list[forms.Row]:
    def value(field: str) -> Any:
        return forms.current(goal, changes, field)

    return [
        ("project_fk", "Project", row_name(db, Project, value("project_fk"))),
        ("name", "Name", value("name") or "—"),
        ("hours", "Hours", f"{value('hours')}h"),
        ("start", "From", str(value("start"))),
        ("deadline", "Deadline", str(value("deadline"))),
    ]


def ask_field(
    db: DBSession,
    prompter: Prompter,
    goal: Goal,
    changes: dict[str, Any],
    field: str,
) -> None:
    value = forms.current(goal, changes, field)

    if field == "project_fk":
        changes["project_fk"] = pick_project(
            prompter, get_projects(db, archived=True), default=value
        )
    elif field == "name":
        changes["name"] = prompter.input(
            "Name", value=value, placeholder="empty for none"
        ).strip()
    elif field == "hours":
        changes["hours"] = parse_hours(
            prompter.input("Hours", value=str(value), validator=hours_validator)
        )
    elif field == "start":
        deadline = forms.current(goal, changes, "deadline")

        def parse(text: str) -> date:
            start = parse_start(text)
            check_goal(1, start, deadline)
            return start

        changes["start"] = parse(
            prompter.input(
                "From",
                value=str(value),
                placeholder=f"{DATE_PLACEHOLDER}; empty for today",
                validator=input_validator(parse),
            )
        )
    elif field == "deadline":
        start = forms.current(goal, changes, "start")
        changes["deadline"] = parse_date(
            prompter.input(
                "Deadline",
                value=str(value),
                placeholder=DATE_PLACEHOLDER,
                validator=deadline_validator(start),
            )
        )


def ask_edits(db: DBSession, prompter: Prompter, goal: Goal) -> dict[str, Any]:
    return forms.ask_changes(
        prompter,
        f"Edit goal #{goal.id}",
        goal,
        rows=lambda changes: field_rows(db, goal, changes),
        ask_field=lambda changes, field: ask_field(db, prompter, goal, changes, field),
    )


def edit_command(ctx: typer.Context, goal_id: IdArgument = None) -> None:
    """
    Edit a goal: its project, name, hours, start and deadline.
    """

    entities.require_terminal("Editing")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        goal = get_or_pick(db, goal_id, "edit")
        changes = commands.run_prompts(
            lambda prompter: ask_edits(db, prompter, goal),
            cancelled="No changes were saved.",
        )

        if not changes:
            print_info(title="Nothing changed", text=goal_label(db, goal))
            return

        try:
            goal = update_goal(db, goal, **changes)
        except ValueError as e:
            print_error(title="Can't save the goal", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="✏️  Edit", text=f"Goal #{goal.id} {goal_label(db, goal)} saved."
        )
