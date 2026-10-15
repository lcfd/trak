"""`trak customers create|show|edit`."""

from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import entities, forms, output
from trak.base_messages import print_error, print_success
from trak.customers import listing
from trak.customers.listing import CustomerFilters, customer_json
from trak.customers.models import Customer
from trak.customers.services import check_customer, create_customer, update_customer
from trak.labels.links import label_details, with_tags
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.commands import CategoryOption, TagsOption
from trak.sessions.display import format_duration
from trak.sessions.editing import ask_label, format_time, label_rows
from trak.sessions.guided import Prompter, ask_category, ask_tags, input_validator
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
            metavar="NAME",
            help="The customer's name. Leave it empty to fill in every field "
            "(in a terminal), starting from the options.",
        ),
    ] = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
) -> None:
    """
    Create a customer. Without a name, asks for every field.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        fields: dict[str, Any] = {
            "category_fk": None,
            "tag_fks": [],
            **commands.find_category(db, category),
        }
        tag_fks = commands.find_tags(db, tags)
        if tag_fks is not None:
            fields["tag_fks"] = tag_fks

        if name is None:
            entities.require_terminal("Creating a customer without a name")

            def ask(prompter: Prompter) -> str:
                answer = prompter.input(
                    "Name", placeholder="e.g. ACME", validator=name_validator(db)
                )
                fields["category_fk"] = ask_category(
                    db, prompter, fields["category_fk"]
                )
                fields["tag_fks"] = ask_tags(db, prompter, fields["tag_fks"])
                return answer

            name = commands.run_prompts(ask, cancelled="No customer was created.")

        try:
            customer = create_customer(db, name=name, **fields)
        except ValueError as e:
            print_error(title="Can't create the customer", text=str(e))
            raise typer.Exit(1)

        output.emit(customer_json(db, customer))
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
        output.emit(customer_json(db, customer))
        print_customer(db, customer)


def print_customer(db: DBSession, customer: Customer) -> None:
    """The panel of `trak customers show`."""

    totals = session_totals(db, customer_fk=customer.id)
    projects = project_names(db, customer)
    entities.print_details(
        title=f"Customer #{customer.id}",
        rows=[
            ("Name", customer_label(customer)),
            *label_details(db, customer),
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
    original: Any = with_tags(db, customer)

    def ask_field(changes: dict[str, Any], field: str) -> None:
        if field != "name":
            value = forms.current(original, changes, field)
            ask_label(db, prompter, changes, field, value)
            return
        changes["name"] = prompter.input(
            "Name",
            value=forms.current(original, changes, "name") or "",
            validator=name_validator(db, customer.id),
        ).strip()

    def value(changes: dict[str, Any], field: str) -> Any:
        return forms.current(original, changes, field)

    return forms.ask_changes(
        prompter,
        f"Edit customer #{customer.id}",
        original,
        rows=lambda changes: [
            ("name", "Name", value(changes, "name") or "—"),
            *label_rows(db, value(changes, "category_fk"), value(changes, "tag_fks")),
        ],
        ask_field=ask_field,
    )


def edit_command(
    ctx: typer.Context,
    customer_id: IdArgument = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="The name.")] = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
) -> None:
    """
    Edit a customer: its name, category and tags (--tag replaces them). With
    options, saves them right away; without, opens the form (terminal).
    """

    given = name is not None or category is not None or tags is not None
    if not given:
        entities.require_terminal("Editing without options")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        customer = get_or_pick(db, customer_id, "edit")
        if given:
            flags: dict[str, Any] = commands.find_category(db, category)
            if name is not None:
                flags["name"] = name.strip()
            tag_fks = commands.find_tags(db, tags)
            if tag_fks is not None:
                flags["tag_fks"] = tag_fks
            changes = forms.effective_changes(with_tags(db, customer), flags)
        else:
            changes = commands.run_prompts(
                lambda prompter: ask_edits(db, prompter, customer),
                cancelled="No changes were saved.",
            )

        entities.save_changes(
            db,
            customer,
            changes,
            update=update_customer,
            noun="customer",
            label=customer_label,
            to_json=lambda c: customer_json(db, c),
        )
