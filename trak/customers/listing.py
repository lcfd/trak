"""`trak customers list`: browse customers, by name."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession
from sqlmodel import func, select

from trak import browser, entities, output, tables
from trak.customers.models import Customer
from trak.customers.services import list_customers
from trak.labels.links import category_name, labels_json, tag_names
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.guided import Prompter
from trak.sessions.listing import ask_name, customer_name
from trak.sessions.services import session_totals


@dataclass
class CustomerFilters:
    name: str = ""
    page: int = 1
    per_page: int = browser.PER_PAGE

    @property
    def active(self) -> bool:
        return bool(self.name)

    def describe(self) -> str:
        return f'name: "{escape(self.name)}"' if self.name else "none"


def query(db: DBSession, filters: CustomerFilters) -> tuple[list[Customer], int]:
    return list_customers(
        db,
        name=filters.name or None,
        limit=filters.per_page,
        offset=(filters.page - 1) * filters.per_page,
    )


def count_projects(db: DBSession, customer: Customer) -> int:
    return db.exec(
        select(func.count())
        .select_from(Project)
        .where(Project.customer_fk == customer.id)
    ).one()


def customer_json(db: DBSession, customer: Customer) -> dict[str, Any]:
    """The Customer for `--json`: its fields, its projects and the time tracked."""

    projects = db.exec(
        select(Project).where(Project.customer_fk == customer.id).order_by(Project.name)
    )
    totals = session_totals(db, customer_fk=customer.id)
    return {
        **output.fields(customer),
        **labels_json(db, customer),
        "projects": [
            {"id": p.id, "name": p.name, "archived": p.archived} for p in projects
        ],
        "sessions": totals.sessions,
        "tracked_seconds": output.seconds(totals.time),
        "last_session": totals.last,
    }


def customer_cells(db: DBSession, customer: Customer) -> tables.Cells:
    """Every cell a customers table can show, as markup."""

    totals = session_totals(db, customer_fk=customer.id)
    category = escape(category_name(db, customer) or "")
    tags = tag_names(db, customer)
    return {
        "id": str(customer.id),
        "name": escape(customer_name(customer)),
        "category": category,
        "tags": escape(", ".join(tags)),
        "labels": " ".join([category, *(f"#{escape(t)}" for t in tags)]).strip(),
        "projects": str(count_projects(db, customer)),
        "sessions": str(totals.sessions),
        "time": format_duration(totals.time),
    }


NAME = tables.col("name", style="green", flex=True)
TIME = tables.col("time", right=True)
# Widest first; see `tables.py`.
LAYOUTS: list[tables.Layout] = [
    [
        tables.ID,
        NAME,
        tables.col("category", style="magenta", optional=True),
        tables.col("tags", style="magenta", optional=True),
        tables.col("projects", right=True),
        tables.col("sessions", right=True),
        TIME,
    ],
    [
        tables.ID,
        NAME,
        tables.col("labels", style="magenta", flex=True, least=10, optional=True),
        tables.col("projects", right=True),
        TIME,
    ],
    [tables.ID, NAME, TIME],
]


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("/", ("/",), "name", "Search by name"),
]
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def show_customer(db: DBSession, customer: Customer, screen: Any) -> None:
    from trak.customers.commands import print_customer

    entities.show_printed(screen, lambda: print_customer(db, customer))


def edit_customer(db: DBSession, customer: Customer, prompter: Prompter) -> str:
    from trak.customers.commands import ask_edits, customer_label
    from trak.customers.services import update_customer

    return entities.edit_in_place(
        db,
        customer,
        prompter,
        ask=ask_edits,
        update=update_customer,
        noun="customer",
        label=customer_label,
    )


def customer_listing(db: DBSession) -> browser.Listing[Customer, CustomerFilters]:
    return browser.Listing(
        show=lambda customer, screen: show_customer(db, customer, screen),
        edit=lambda customer, prompter: edit_customer(db, customer, prompter),
        noun="customer",
        query=lambda filters: query(db, filters),
        cells=lambda customer: customer_cells(db, customer),
        layouts=LAYOUTS,
        to_json=lambda customer: customer_json(db, customer),
        filter_shortcuts=FILTER_SHORTCUTS,
        ask_filter=lambda prompter, filters, action: ask_name(prompter, filters),  # type: ignore[arg-type]
        clear=lambda filters: CustomerFilters(per_page=filters.per_page),
    )


def browse(
    db: DBSession,
    prompter: Prompter,
    filters: CustomerFilters,
    read_key: Callable[[], str] | None = None,
    pick: bool = False,
    title: str = "Customers",
    fit: bool = True,
) -> Customer | None:
    """Browse the customers until the user quits (None), or pick one."""

    return browser.browse(
        customer_listing(db),
        prompter,
        filters,
        read_key=read_key,
        pick=pick,
        title=title,
        fit=fit,
    )


def list_command(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option(
            "--name", "-n", help="Only the customers whose name contains this."
        ),
    ] = None,
    page: Annotated[int, typer.Option("--page", min=1, help="The page to show.")] = 1,
    per_page: Annotated[
        int | None,
        typer.Option(
            "--per-page",
            min=1,
            max=500,
            help="Customers per page. Default: what fits the terminal; 20 when printed.",
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
    Browse customers by name. The option sets the starting filter.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        filters = CustomerFilters(
            name=name or "", page=page, per_page=per_page or browser.PER_PAGE
        )

        if plain or not commands.is_interactive():
            browser.print_page(customer_listing(db), filters)
            return

        entities.run_browser(
            lambda prompter: browse(db, prompter, filters, fit=per_page is None)
        )
