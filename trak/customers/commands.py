"""`trak customers create|show|edit`."""

from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import entities, forms
from trak.base_messages import print_error, print_info, print_success
from trak.customers import listing
from trak.customers.listing import CustomerFilters
from trak.customers.models import Customer
from trak.customers.services import check_customer, create_customer, update_customer
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.editing import format_time
from trak.sessions.guided import Prompter, input_validator
from trak.sessions.listing import customer_name
from trak.sessions.services import session_totals


def name_validator(db: DBSession, customer_id: int | None = None) -> Any:
    return input_validator(
        lambda text: check_customer(db, text.strip(), customer_id=customer_id)
    )


def customer_label(customer: Customer) -> str:
    return f"[green]{escape(customer_name(customer))}[/green]"


# trak customers create


def create_command(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(
            metavar="NAME", help="The customer's name. Leave it empty to type it."
        ),
    ] = None,
) -> None:
    """
    Create a customer.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        if name is None:
            entities.require_terminal("Creating a customer without a name")
            name = commands.run_prompts(
                lambda prompter: prompter.input(
                    "Name", placeholder="e.g. ACME", validator=name_validator(db)
                ),
                cancelled="No customer was created.",
            )

        try:
            customer = create_customer(db, name=name)
        except ValueError as e:
            print_error(title="Can't create the customer", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="✨ Create",
            text=f"Customer #{customer.id} {customer_label(customer)} created.",
        )


# trak customers show / edit


IdArgument = Annotated[
    int | None,
    typer.Argument(
        metavar="ID", help="The customer. Leave it empty to pick one from the list."
    ),
]


def get_or_pick(db: DBSession, customer_id: int | None, verb: str) -> Customer:
    return entities.get_or_pick(
        db,
        Customer,
        customer_id,
        lambda prompter: listing.browse(
            db,
            prompter,
            CustomerFilters(),
            pick=True,
            title=f"Pick a customer to {verb}",
        ),
        noun="customer",
        command=f"trak customers {verb}",
        cancelled=f"No customer was {'shown' if verb == 'show' else 'edited'}.",
    )


def project_names(db: DBSession, customer: Customer) -> str:
    projects = db.exec(
        select(Project).where(Project.customer_fk == customer.id).order_by(Project.name)
    )
    return ", ".join(
        escape(p.name) + (" [dim](archived)[/dim]" if p.archived else "")
        for p in projects
    )


def show_command(ctx: typer.Context, customer_id: IdArgument = None) -> None:
    """
    Show a customer: its projects and the time tracked for it.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        customer = get_or_pick(db, customer_id, "show")
        totals = session_totals(db, customer_fk=customer.id)
        projects = project_names(db, customer)
        entities.print_details(
            title=f"Customer #{customer.id}",
            rows=[
                ("Name", customer_label(customer)),
                ("Projects", projects or "[dim]—[/dim]"),
                ("Sessions", str(totals.sessions)),
                ("Time", format_duration(totals.time)),
                (
                    "Last session",
                    entities.or_dash(totals.last and format_time(totals.last)),
                ),
            ],
            hint=f'Edit it with "trak customers edit {customer.id}".',
        )


def ask_edits(db: DBSession, prompter: Prompter, customer: Customer) -> dict[str, Any]:
    def ask_field(changes: dict[str, Any], field: str) -> None:
        changes["name"] = prompter.input(
            "Name",
            value=forms.current(customer, changes, "name") or "",
            validator=name_validator(db, customer.id),
        ).strip()

    return forms.ask_changes(
        prompter,
        f"Edit customer #{customer.id}",
        customer,
        rows=lambda changes: [
            ("name", "Name", forms.current(customer, changes, "name") or "—")
        ],
        ask_field=ask_field,
    )


def edit_command(ctx: typer.Context, customer_id: IdArgument = None) -> None:
    """
    Edit a customer's name.
    """

    entities.require_terminal("Editing")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        customer = get_or_pick(db, customer_id, "edit")
        changes = commands.run_prompts(
            lambda prompter: ask_edits(db, prompter, customer),
            cancelled="No changes were saved.",
        )

        if not changes:
            print_info(title="Nothing changed", text=customer_label(customer))
            return

        try:
            customer = update_customer(db, customer, **changes)
        except ValueError as e:
            print_error(title="Can't save the customer", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="✏️  Edit",
            text=f"Customer #{customer.id} {customer_label(customer)} saved.",
        )
