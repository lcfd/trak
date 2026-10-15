"""`trak projects create|edit|report` (`show` is in view.py)."""

import shlex
from datetime import date
from typing import Annotated, Any

import click
import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, forms, output
from trak.base_messages import print_error, print_success
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.dates import DATE_PLACEHOLDER, parse_date, parse_optional_date, today
from trak.goals.display import format_day
from trak.labels.links import with_tags
from trak.projects import listing, report
from trak.projects.listing import ProjectFilters, format_rate, project_json
from trak.projects.models import Project
from trak.projects.services import (
    check_dates,
    check_project,
    create_project,
    update_project,
)
from trak.sessions import commands
from trak.sessions.commands import CategoryOption, TagsOption
from trak.sessions.editing import ask_label, label_rows, row_name
from trak.sessions.guided import (
    Prompter,
    ask_category,
    ask_tags,
    input_validator,
    pick,
)

RATE_PLACEHOLDER = "per hour, a whole number; empty for none"
OPTIONAL_DATE_PLACEHOLDER = f"{DATE_PLACEHOLDER}; empty for none"


def parse_rate(value: str) -> int:
    """A rate typed by the user; empty means 0."""

    value = value.strip()
    if not value:
        return 0
    if not value.isdigit():
        raise ValueError("the rate must be a whole number, 0 or more")
    return int(value)


rate_validator = input_validator(parse_rate)


def name_validator(db: DBSession, project_id: int | None = None) -> Any:
    return input_validator(
        lambda text: check_project(db, text.strip(), 0, project_id=project_id)
    )


def dates_validator(start: date | None = None, end: date | None = None) -> Any:
    """Accepts an optional day; `start` or `end` is the other end to respect."""

    def parse(text: str) -> date | None:
        day = parse_optional_date(text)
        if start is not None:
            check_dates(start, day)
        if end is not None:
            check_dates(day, end)
        return day

    return input_validator(parse)


def ask_start(prompter: Prompter, value: date | None, end: date | None) -> date | None:
    return parse_optional_date(
        prompter.input(
            "Start",
            value=str(value or ""),
            placeholder=OPTIONAL_DATE_PLACEHOLDER,
            validator=dates_validator(end=end),
        )
    )


def ask_end(prompter: Prompter, value: date | None, start: date | None) -> date | None:
    return parse_optional_date(
        prompter.input(
            "End",
            value=str(value or ""),
            placeholder=OPTIONAL_DATE_PLACEHOLDER,
            validator=dates_validator(start=start),
        )
    )


def end_text(project: Project, on: date | None = None) -> str | None:
    """The end day, with the days left until it; None without an end."""

    if project.end is None:
        return None
    days = (project.end - (on or today())).days
    if days < 0:
        left = f"ended {-days} day{'s' if days < -1 else ''} ago"
    elif days == 0:
        left = "ends today"
    else:
        left = f"{days} day{'s' if days > 1 else ''} left"
    return f"{format_day(project.end)} [dim]· {left}[/dim]"


def project_label(project: Project) -> str:
    return f"[green]{escape(project.name)}[/green]"


# trak projects create


def ask_new_project(
    db: DBSession, prompter: Prompter, defaults: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """
    Ask for every field of a new Project, with `defaults` (from the flags)
    already filled in. None means the user gave up.
    """

    defaults = defaults or {}
    fields: dict[str, Any] = {
        "name": prompter.input(
            "Name", placeholder="e.g. Website", validator=name_validator(db)
        ).strip()
    }
    customers = get_customers(db)
    if customers:
        fields["customer_fk"] = pick(
            prompter, "Customer", customers, default=defaults.get("customer_fk")
        )
    rate = defaults.get("rate", 0)
    fields["rate"] = parse_rate(
        prompter.input(
            "Rate",
            default=str(rate) if rate else "",
            placeholder=RATE_PLACEHOLDER,
            validator=rate_validator,
        )
    )
    fields["description"] = prompter.input(
        "Description", default=defaults.get("description", ""), placeholder="optional"
    ).strip()
    fields["category_fk"] = ask_category(db, prompter, defaults.get("category_fk"))
    fields["tag_fks"] = ask_tags(db, prompter, defaults.get("tag_fks", []))
    fields["start"] = ask_start(prompter, defaults.get("start"), None)
    fields["end"] = ask_end(prompter, defaults.get("end"), fields["start"])

    if not prompter.confirm("Create this project?"):
        return None
    return fields


def create_command(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(
            metavar="NAME",
            help="The project's name. Leave it empty to fill in every field "
            "(in a terminal), starting from the options.",
        ),
    ] = None,
    customer_name: Annotated[
        str | None,
        typer.Option("--customer", "-c", help="The customer of the project."),
    ] = None,
    rate: Annotated[
        int, typer.Option("--rate", "-r", min=0, help="The hourly rate.")
    ] = 0,
    description: Annotated[
        str, typer.Option("--description", "-d", help="A description.")
    ] = "",
    start: Annotated[
        str | None,
        typer.Option(
            "--start",
            "-s",
            metavar="DATE",
            help=f"The day it starts: {DATE_PLACEHOLDER}.",
        ),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            "-e",
            metavar="DATE",
            help=f"The day it ends (included): {DATE_PLACEHOLDER}.",
        ),
    ] = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
) -> None:
    """
    Create a project. Without a name, asks for every field.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        defaults: dict[str, Any] = {"rate": rate, "description": description}
        try:
            defaults["start"] = parse_date(start) if start is not None else None
            defaults["end"] = parse_date(end) if end is not None else None
        except ValueError as e:
            commands.fail("Can't create the project", e)
        if customer_name is not None:
            customer = commands.find_customer(db, customer_name)
            if customer is None:
                raise typer.Exit(1)
            defaults["customer_fk"] = customer.id
        defaults.update(commands.find_category(db, category))
        tag_fks = commands.find_tags(db, tags)
        if tag_fks is not None:
            defaults["tag_fks"] = tag_fks

        if name is None:
            entities.require_terminal("Creating a project without a name")
            fields = commands.run_prompts(
                lambda prompter: ask_new_project(db, prompter, defaults),
                cancelled="No project was created.",
            )
            if fields is None:
                commands.cancel("No project was created.")
        else:
            fields = {"name": name, **defaults}

        try:
            project = create_project(db, **fields)
        except ValueError as e:
            commands.fail("Can't create the project", e)

        output.emit(project_json(db, project))
        print_success(
            title="✨ Create",
            text=(
                f"Project #{project.id} {project_label(project)} created.\n\n"
                f'Start tracking it with "trak start {shlex.quote(project.name)}".'
            ),
        )


# trak projects show / edit


IdArgument = Annotated[
    int | None,
    typer.Argument(
        metavar="ID", help="The project. Leave it empty to pick one from the list."
    ),
]


CANCELLED = {
    "show": "No project was shown.",
    "edit": "No project was edited.",
    "report": "No report was shown.",
}


def get_or_pick(db: DBSession, project_id: int | None, verb: str) -> Project:
    return entities.get_or_pick(
        db,
        Project,
        project_id,
        lambda prompter: listing.browse(
            db,
            prompter,
            ProjectFilters(archived=True),
            pick=True,
            title=f"Pick a project to {verb}",
        ),
        noun="project",
        command=f"trak projects {verb}",
        cancelled=CANCELLED[verb],
    )


def customer_of(db: DBSession, project: Project) -> str | None:
    if project.customer_fk is None:
        return None
    return row_name(db, Customer, project.customer_fk)


def field_rows(
    db: DBSession, project: Project, changes: dict[str, Any]
) -> list[forms.Row]:
    def value(field: str) -> Any:
        return forms.current(project, changes, field)

    return [
        ("name", "Name", value("name")),
        ("customer_fk", "Customer", row_name(db, Customer, value("customer_fk"))),
        *label_rows(db, value("category_fk"), value("tag_fks")),
        ("rate", "Rate", format_rate(value("rate")) or "—"),
        ("description", "Description", value("description") or "—"),
        ("start", "Start", str(value("start") or "—")),
        ("end", "End", str(value("end") or "—")),
        ("archived", "Archived", "yes" if value("archived") else "no"),
    ]


def ask_field(
    db: DBSession,
    prompter: Prompter,
    project: Project,
    changes: dict[str, Any],
    field: str,
) -> None:
    value = forms.current(project, changes, field)

    if field == "name":
        changes["name"] = prompter.input(
            "Name", value=value, validator=name_validator(db, project.id)
        ).strip()
    elif field == "customer_fk":
        changes["customer_fk"] = pick(
            prompter, "Customer", get_customers(db), default=value
        )
    elif field in ("category_fk", "tag_fks"):
        ask_label(db, prompter, changes, field, value)
    elif field == "rate":
        changes["rate"] = parse_rate(
            prompter.input(
                "Rate",
                value=str(value) if value else "",
                placeholder=RATE_PLACEHOLDER,
                validator=rate_validator,
            )
        )
    elif field == "description":
        changes["description"] = prompter.input(
            "Description", value=value, placeholder="empty for none"
        ).strip()
    elif field == "start":
        changes["start"] = ask_start(
            prompter, value, forms.current(project, changes, "end")
        )
    elif field == "end":
        changes["end"] = ask_end(
            prompter, value, forms.current(project, changes, "start")
        )
    elif field == "archived":
        changes["archived"] = forms.ask_yes_no(prompter, "Archived", value)


def ask_edits(db: DBSession, prompter: Prompter, project: Project) -> dict[str, Any]:
    original: Any = with_tags(db, project)
    return forms.ask_changes(
        prompter,
        f"Edit project #{project.id}",
        original,
        rows=lambda changes: field_rows(db, original, changes),
        ask_field=lambda changes, field: ask_field(
            db, prompter, original, changes, field
        ),
    )


def flag_changes(
    db: DBSession,
    *,
    name: str | None = None,
    customer: str | None = None,
    rate: int | None = None,
    description: str | None = None,
    start: str | None = None,
    end: str | None = None,
    archived: bool | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    The changes the flags of `trak projects edit` ask for; None means the
    flag wasn't given. Exits with 1, after the error, on a bad value.
    """

    changes: dict[str, Any] = {
        field: value
        for field, value in (
            ("name", name),
            ("rate", rate),
            ("description", description),
            ("archived", archived),
        )
        if value is not None
    }
    if customer is not None:
        changes["customer_fk"] = None
        if customer.strip():
            found = commands.find_customer(db, customer.strip())
            if found is None:
                raise typer.Exit(1)
            changes["customer_fk"] = found.id
    changes.update(commands.find_category(db, category))
    tag_fks = commands.find_tags(db, tags)
    if tag_fks is not None:
        changes["tag_fks"] = tag_fks
    try:
        if start is not None:
            changes["start"] = parse_optional_date(start)
        if end is not None:
            changes["end"] = parse_optional_date(end)
    except ValueError as e:
        commands.fail("Can't save the project", e)
    return changes


def edit_command(
    ctx: typer.Context,
    project_id: IdArgument = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="The name.")] = None,
    customer: Annotated[
        str | None,
        typer.Option("--customer", "-c", help="The customer, by name. Empty for none."),
    ] = None,
    rate: Annotated[
        int | None,
        typer.Option("--rate", "-r", min=0, help="The hourly rate; 0 for none."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="The description. Empty for none."),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option(
            "--start",
            "-s",
            metavar="DATE",
            help=f"The day it starts: {DATE_PLACEHOLDER}. Empty for none.",
        ),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            "-e",
            metavar="DATE",
            help=f"The day it ends: {DATE_PLACEHOLDER}. Empty for none.",
        ),
    ] = None,
    archived: Annotated[
        bool | None,
        typer.Option("--archive/--unarchive", help="Archive it, or bring it back."),
    ] = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
) -> None:
    """
    Edit a project: its name, customer, category, tags (--tag replaces them),
    rate, description, start and end days and whether it's archived. With options, saves them right away; without,
    opens the form (terminal).
    """

    flags = {
        "name": name,
        "customer": customer,
        "rate": rate,
        "description": description,
        "start": start,
        "end": end,
        "archived": archived,
        "category": category,
        "tags": tags,
    }
    given = any(value is not None for value in flags.values())
    if not given:
        entities.require_terminal("Editing without options")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = get_or_pick(db, project_id, "edit")
        if given:
            changes = forms.effective_changes(
                with_tags(db, project), flag_changes(db, **flags)
            )
        else:
            changes = commands.run_prompts(
                lambda prompter: ask_edits(db, prompter, project),
                cancelled="No changes were saved.",
            )

        entities.save_changes(
            db,
            project,
            changes,
            update=update_project,
            noun="project",
            label=project_label,
            to_json=lambda p: project_json(db, p),
        )


# trak projects report


def report_command(
    ctx: typer.Context,
    project_id: IdArgument = None,
    range_key: Annotated[
        str | None,
        typer.Option(
            "--range",
            "-r",
            click_type=click.Choice(report.RANGE_KEYS),
            help="The range to start from (default: since the start).",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--from",
            help=f"Report from this day instead of a range: {DATE_PLACEHOLDER}. "
            "Default: the project's first day.",
        ),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option(
            "--to",
            help="Report up to this day (included) instead of a range. Default: today.",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain", help="Print the report and exit, instead of browsing it."
        ),
    ] = False,
) -> None:
    """
    Report the time tracked on a project, as a bar chart per day (or week,
    month, year). In a terminal it stays open: Tab switches the range, h/l
    select a bar, Enter zooms into it (its months, weeks or days), Esc zooms
    out.
    """

    if range_key is not None and (since is not None or until is not None):
        print_error(
            title="Can't report", text="Give either --range or --from/--to, not both."
        )
        raise typer.Exit(1)

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = get_or_pick(db, project_id, "report")
        try:
            custom = report.asked_range(db, project, since, until)
        except ValueError as e:
            commands.fail("Can't report", e)

        if output.json_mode():
            output.emit(report.report_json(db, project, range_key, custom=custom))
            return

        if plain or not commands.is_interactive():
            report.print_report(db, project, range_key, custom=custom)
            return

        try:
            report.show(db, project, range_key, custom=custom)
        except KeyboardInterrupt:
            # Ctrl-C is a normal way to leave the report.
            pass
