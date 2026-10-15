"""`trak customers list`: browse customers, by name."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import typer
from rich.markup import escape
from rich.table import Table
from sqlmodel import Session as DBSession
from sqlmodel import func, select

from trak import browser, entities, output
from trak.customers.models import Customer
from trak.customers.services import list_customers
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
    per_page: int = 20

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
        "projects": [
            {"id": p.id, "name": p.name, "archived": p.archived} for p in projects
        ],
        "sessions": totals.sessions,
        "tracked_seconds": output.seconds(totals.time),
        "last_session": totals.last,
    }


def build_table(
    db: DBSession, customers: list[Customer], cursor: int | None = None
) -> Table:
    """The customers table; the row at `cursor`, if any, is highlighted."""

    table = Table(header_style="bold", show_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Projects", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Time", justify="right")

    for index, customer in enumerate(customers):
        totals = session_totals(db, customer_fk=customer.id)
        table.add_row(
            str(customer.id),
            escape(customer_name(customer)),
            str(count_projects(db, customer)),
            str(totals.sessions),
            format_duration(totals.time),
            style="reverse" if index == cursor else None,
        )
    return table


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("/", ("/",), "name", "Search by name"),
]
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def customer_listing(db: DBSession) -> browser.Listing[Customer, CustomerFilters]:
    return browser.Listing(
        noun="customer",
        query=lambda filters: query(db, filters),
        table=lambda customers, cursor: build_table(db, customers, cursor),
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
) -> Customer | None:
    """Browse the customers until the user quits (None), or pick one."""

    return browser.browse(
        customer_listing(db),
        prompter,
        filters,
        read_key=read_key,
        pick=pick,
        title=title,
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
        int, typer.Option("--per-page", min=1, max=500, help="Customers per page.")
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
    Browse customers by name. The option sets the starting filter.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        filters = CustomerFilters(name=name or "", page=page, per_page=per_page)

        if plain or not commands.is_interactive():
            browser.print_page(customer_listing(db), filters)
            return

        entities.run_browser(lambda prompter: browse(db, prompter, filters))
