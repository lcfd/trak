"""`trak projects create|show|edit`."""

import shlex
from typing import Annotated, Any

import click
import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, forms
from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.projects import listing, report
from trak.projects.listing import ProjectFilters, format_rate
from trak.projects.models import Project
from trak.projects.services import check_project, create_project, update_project
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.editing import format_time, row_name
from trak.sessions.guided import Prompter, input_validator, pick
from trak.sessions.services import session_totals

RATE_PLACEHOLDER = "per hour, a whole number; empty for none"


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


def project_label(project: Project) -> str:
    return f"[green]{escape(project.name)}[/green]"


# trak projects create


def ask_new_project(db: DBSession, prompter: Prompter) -> dict[str, Any] | None:
    """Ask for every field of a new Project. None means the user gave up."""

    fields: dict[str, Any] = {
        "name": prompter.input(
            "Name", placeholder="e.g. Website", validator=name_validator(db)
        ).strip()
    }
    customers = get_customers(db)
    if customers:
        fields["customer_fk"] = pick(prompter, "Customer", customers)
    fields["rate"] = parse_rate(
        prompter.input("Rate", placeholder=RATE_PLACEHOLDER, validator=rate_validator)
    )
    fields["description"] = prompter.input(
        "Description", placeholder="optional"
    ).strip()

    if not prompter.confirm("Create this project?"):
        return None
    return fields


def create_command(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(
            metavar="NAME",
            help="The project's name. Leave it empty to fill in every field.",
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
) -> None:
    """
    Create a project. Without a name, asks for every field.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        if name is None:
            entities.require_terminal("Creating a project without a name")
            fields = commands.run_prompts(
                lambda prompter: ask_new_project(db, prompter),
                cancelled="No project was created.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No project was created.")
                raise typer.Exit(1)
        else:
            fields = {"name": name, "rate": rate, "description": description}
            if customer_name is not None:
                customer = commands.find_customer(db, customer_name)
                if customer is None:
                    raise typer.Exit(1)
                fields["customer_fk"] = customer.id

        try:
            project = create_project(db, **fields)
        except ValueError as e:
            print_error(title="Can't create the project", text=str(e))
            raise typer.Exit(1)

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


def show_command(ctx: typer.Context, project_id: IdArgument = None) -> None:
    """
    Show a project: its fields and the time tracked on it.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = get_or_pick(db, project_id, "show")
        totals = session_totals(db, project_fk=project.id)
        entities.print_details(
            title=f"Project #{project.id}",
            rows=[
                ("Name", project_label(project)),
                ("Customer", entities.or_dash(customer_of(db, project))),
                ("Rate", entities.or_dash(format_rate(project.rate))),
                ("Description", entities.or_dash(project.description)),
                ("Status", "archived" if project.archived else "active"),
                ("Sessions", str(totals.sessions)),
                ("Time", format_duration(totals.time)),
                (
                    "Last session",
                    entities.or_dash(totals.last and format_time(totals.last)),
                ),
            ],
            hint=f'Edit it with "trak projects edit {project.id}".',
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
        ("rate", "Rate", format_rate(value("rate")) or "—"),
        ("description", "Description", value("description") or "—"),
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
    elif field == "archived":
        changes["archived"] = forms.ask_yes_no(prompter, "Archived", value)


def ask_edits(db: DBSession, prompter: Prompter, project: Project) -> dict[str, Any]:
    return forms.ask_changes(
        prompter,
        f"Edit project #{project.id}",
        project,
        rows=lambda changes: field_rows(db, project, changes),
        ask_field=lambda changes, field: ask_field(
            db, prompter, project, changes, field
        ),
    )


def edit_command(ctx: typer.Context, project_id: IdArgument = None) -> None:
    """
    Edit a project: its name, customer, rate, description and whether it's archived.
    """

    entities.require_terminal("Editing")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = get_or_pick(db, project_id, "edit")
        changes = commands.run_prompts(
            lambda prompter: ask_edits(db, prompter, project),
            cancelled="No changes were saved.",
        )

        if not changes:
            print_info(title="Nothing changed", text=project_label(project))
            return

        try:
            project = update_project(db, project, **changes)
        except ValueError as e:
            print_error(title="Can't save the project", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="✏️  Edit",
            text=f"Project #{project.id} {project_label(project)} saved.",
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
    plain: Annotated[
        bool,
        typer.Option(
            "--plain", help="Print the report and exit, instead of browsing it."
        ),
    ] = False,
) -> None:
    """
    Report the time tracked on a project, as a bar chart per day (or week,
    month, year). In a terminal it stays open: h/l switch the range.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = get_or_pick(db, project_id, "report")

        if plain or not commands.is_interactive():
            report.print_report(db, project, range_key)
            return

        try:
            report.show(db, project, range_key)
        except KeyboardInterrupt:
            # Ctrl-C is a normal way to leave the report.
            pass
