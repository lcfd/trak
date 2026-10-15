"""`trak goals create|show|edit`."""

from datetime import date
from typing import Annotated, Any

import typer
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession

from trak import entities, forms, output
from trak.base_messages import print_error, print_success, print_warning
from trak.dates import DATE_PLACEHOLDER, parse_date
from trak.goals import listing
from trak.goals.display import (
    days_text,
    format_day,
    goal_json,
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


def parse_hours(value: str) -> int:
    value = value.strip()
    if not value.isdigit() or int(value) == 0:
        raise ValueError("the hours must be a whole number, 1 or more")
    return int(value)


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
    db: DBSession,
    prompter: Prompter,
    project: Project | None = None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Ask for every field of a new Goal, with `defaults` (from the flags)
    already filled in. None means the user gave up.
    """

    defaults = defaults or {}
    fields: dict[str, Any] = {}
    if project is None:
        fields["project_fk"] = pick_project(prompter, get_projects(db))
        project = db.get(Project, fields["project_fk"])
        assert project is not None
    else:
        fields["project_fk"] = project.id
    fields["name"] = prompter.input(
        "Name", default=defaults.get("name", ""), placeholder="optional, e.g. Launch"
    ).strip()
    hours = defaults.get("hours")
    fields["hours"] = parse_hours(
        prompter.input(
            "Hours",
            default=str(hours) if hours else "",
            placeholder="e.g. 40",
            validator=hours_validator,
        )
    )
    start = defaults.get("start")
    fields["start"] = parse_start(
        prompter.input(
            "From",
            default=str(start) if start else "",
            placeholder=f"{DATE_PLACEHOLDER}; empty for today",
            validator=start_validator,
        )
    )
    # The project's end is the natural deadline.
    fields["deadline"] = parse_date(
        prompter.input(
            "Deadline",
            value=str(defaults.get("deadline") or project.end or ""),
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
            "--by",
            "-b",
            metavar="DATE",
            help=f"The deadline: {DATE_PLACEHOLDER}. The project's end if not given.",
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
    Create a goal: hours to track on a project by a deadline. Without the
    project, the hours or the deadline, asks for every field (in a terminal),
    starting from the options.
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

        project = None
        if project_name is not None:
            project = commands.find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)

        try:
            defaults: dict[str, Any] = {
                "name": name,
                "hours": hours,
                "start": parse_date(start) if start is not None else None,
                # The project's end is the natural deadline.
                "deadline": (
                    parse_date(deadline)
                    if deadline is not None
                    else project.end
                    if project
                    else None
                ),
            }
        except ValueError as e:
            commands.fail("Can't create the goal", e)

        if project is not None and hours is not None and defaults["deadline"]:
            fields = {"project_fk": project.id, **defaults}
        else:
            if project is None:
                entities.require_terminal("Creating a goal without a project")
            elif not commands.is_interactive():
                print_error(
                    title="Can't create the goal",
                    text=(
                        "Give it the hours and the deadline, e.g.\n\n"
                        f'trak goals create "{project.name}" --hours 40 --by +30'
                    ),
                )
                raise typer.Exit(1)
            fields = commands.run_prompts(
                lambda prompter: ask_new_goal(db, prompter, project, defaults),
                cancelled="No goal was created.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No goal was created.")
                raise typer.Exit(1)

        try:
            goal = create_goal(db, **fields)
        except ValueError as e:
            commands.fail("Can't create the goal", e)

        output.emit(goal_json(db, goal))
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
        output.emit(goal_json(db, goal))
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


def flag_changes(
    db: DBSession,
    *,
    project: str | None = None,
    name: str | None = None,
    hours: int | None = None,
    start: str | None = None,
    deadline: str | None = None,
) -> dict[str, Any]:
    """
    The changes the flags of `trak goals edit` ask for; None means the flag
    wasn't given. Exits with 1, after the error, on a bad value.
    """

    changes: dict[str, Any] = {}
    if project is not None:
        found = commands.find_project(db, project, archived=True)
        if found is None:
            raise typer.Exit(1)
        changes["project_fk"] = found.id
    if name is not None:
        changes["name"] = name.strip()
    if hours is not None:
        changes["hours"] = hours
    try:
        if start is not None:
            changes["start"] = parse_start(start)
        if deadline is not None:
            changes["deadline"] = parse_date(deadline)
    except ValueError as e:
        commands.fail("Can't save the goal", e)
    return changes


def edit_command(
    ctx: typer.Context,
    goal_id: IdArgument = None,
    project: Annotated[
        str | None, typer.Option("--project", "-p", help="The project, by name.")
    ] = None,
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="The name. Empty for none.")
    ] = None,
    hours: Annotated[
        int | None, typer.Option("--hours", "-H", min=1, help="The hours to reach.")
    ] = None,
    start: Annotated[
        str | None,
        typer.Option(
            "--from",
            "-f",
            metavar="DATE",
            help=f"Count the time tracked from this day: {DATE_PLACEHOLDER}.",
        ),
    ] = None,
    deadline: Annotated[
        str | None,
        typer.Option(
            "--by", "-b", metavar="DATE", help=f"The deadline: {DATE_PLACEHOLDER}."
        ),
    ] = None,
) -> None:
    """
    Edit a goal: its project, name, hours, start and deadline. With options,
    saves them right away; without, opens the form (terminal).
    """

    flags = {
        "project": project,
        "name": name,
        "hours": hours,
        "start": start,
        "deadline": deadline,
    }
    given = any(value is not None for value in flags.values())
    if not given:
        entities.require_terminal("Editing without options")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        goal = get_or_pick(db, goal_id, "edit")
        if given:
            changes = forms.effective_changes(goal, flag_changes(db, **flags))
        else:
            changes = commands.run_prompts(
                lambda prompter: ask_edits(db, prompter, goal),
                cancelled="No changes were saved.",
            )

        entities.save_changes(
            db,
            goal,
            changes,
            update=update_goal,
            noun="goal",
            label=lambda g: goal_label(db, g),
            to_json=lambda g: goal_json(db, g),
        )
