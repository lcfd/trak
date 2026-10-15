"""`trak projects list`: browse projects, by name."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table
from sqlmodel import Session as DBSession

from trak import browser, entities
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.projects.services import list_projects
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.guided import Prompter
from trak.sessions.listing import ask_customer, ask_name, customer_name
from trak.sessions.services import session_totals


@dataclass
class ProjectFilters:
    name: str = ""
    customer: Customer | None = None
    archived: bool = False
    page: int = 1
    per_page: int = 20

    @property
    def active(self) -> bool:
        return bool(self.name or self.customer or self.archived)

    def describe(self) -> str:
        parts = []
        if self.name:
            parts.append(f'name: "{escape(self.name)}"')
        if self.customer:
            parts.append(f"customer: {escape(customer_name(self.customer))}")
        if self.archived:
            parts.append("with archived")
        return " · ".join(parts) or "none"


def query(db: DBSession, filters: ProjectFilters) -> tuple[list[Project], int]:
    return list_projects(
        db,
        name=filters.name or None,
        customer_fk=filters.customer.id if filters.customer else None,
        archived=filters.archived,
        limit=filters.per_page,
        offset=(filters.page - 1) * filters.per_page,
    )


def format_rate(rate: int) -> str:
    return f"{rate}/h" if rate else ""


def build_table(
    db: DBSession, projects: list[Project], cursor: int | None = None
) -> Table:
    """The projects table; the row at `cursor`, if any, is highlighted."""

    table = Table(header_style="bold", show_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="green")
    table.add_column("Customer")
    table.add_column("Rate", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Time", justify="right")
    table.add_column("Status")

    for index, project in enumerate(projects):
        customer = (
            db.get(Customer, project.customer_fk) if project.customer_fk else None
        )
        totals = session_totals(db, project_fk=project.id)
        table.add_row(
            str(project.id),
            escape(project.name),
            escape(customer_name(customer)) if customer else "",
            format_rate(project.rate),
            str(totals.sessions),
            format_duration(totals.time),
            "[dim]archived[/dim]" if project.archived else "",
            style="reverse" if index == cursor else None,
        )
    return table


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("/", ("/",), "name", "Search by name"),
    ("c", ("c",), "customer", "Filter by customer"),
    ("a", ("a",), "archived", "Show or hide archived projects"),
]
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def ask_filter(
    db: DBSession, prompter: Prompter, filters: ProjectFilters, action: str
) -> ProjectFilters:
    if action == "customer":
        return ask_customer(db, prompter, filters)  # type: ignore[arg-type]
    return ask_name(prompter, filters)  # type: ignore[arg-type]


def project_listing(db: DBSession) -> browser.Listing[Project, ProjectFilters]:
    return browser.Listing(
        noun="project",
        query=lambda filters: query(db, filters),
        table=lambda projects, cursor: build_table(db, projects, cursor),
        filter_shortcuts=FILTER_SHORTCUTS,
        ask_filter=lambda prompter, filters, action: ask_filter(
            db, prompter, filters, action
        ),
        clear=lambda filters: ProjectFilters(per_page=filters.per_page),
        toggles={
            "archived": lambda filters: replace(
                filters, archived=not filters.archived, page=1
            )
        },
    )


def browse(
    db: DBSession,
    prompter: Prompter,
    filters: ProjectFilters,
    read_key: Callable[[], str] | None = None,
    pick: bool = False,
    title: str = "Projects",
) -> Project | None:
    """Browse the projects until the user quits (None), or pick one."""

    return browser.browse(
        project_listing(db),
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
            "--name", "-n", help="Only the projects whose name contains this."
        ),
    ] = None,
    customer_name_: Annotated[
        str | None,
        typer.Option("--customer", "-c", help="Only the projects of this customer."),
    ] = None,
    archived: Annotated[
        bool,
        typer.Option("--archived", "-a", help="Include archived projects."),
    ] = False,
    page: Annotated[int, typer.Option("--page", min=1, help="The page to show.")] = 1,
    per_page: Annotated[
        int, typer.Option("--per-page", min=1, max=500, help="Projects per page.")
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
    Browse projects by name. The options set the starting filters.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        customer = None
        if customer_name_ is not None:
            customer = commands.find_customer(db, customer_name_)
            if customer is None:
                raise typer.Exit(1)

        filters = ProjectFilters(
            name=name or "",
            customer=customer,
            archived=archived,
            page=page,
            per_page=per_page,
        )

        if plain or not commands.is_interactive():
            browser.print_page(project_listing(db), filters)
            return

        entities.run_browser(lambda prompter: browse(db, prompter, filters))
