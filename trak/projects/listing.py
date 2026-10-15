"""`trak projects list`: browse projects, by name."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import browser, entities, output, tables, tui
from trak.customers.models import Customer
from trak.labels.links import category_name, labels_json, tag_names
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
    per_page: int = browser.PER_PAGE

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


def format_dates(project: Project) -> str:
    """ "2026-10-01 → 2026-12-31", "from 2026-10-01", "until 2026-12-31"."""

    if project.start and project.end:
        return f"{project.start} → {project.end}"
    if project.start:
        return f"from {project.start}"
    if project.end:
        return f"until {project.end}"
    return ""


def project_json(db: DBSession, project: Project) -> dict[str, Any]:
    """The Project for `--json`: its fields, its customer and the time tracked."""

    customer = db.get(Customer, project.customer_fk) if project.customer_fk else None
    totals = session_totals(db, project_fk=project.id)
    return {
        **output.fields(project),
        "customer": customer.name if customer else None,
        **labels_json(db, project),
        "sessions": totals.sessions,
        "tracked_seconds": output.seconds(totals.time),
        "last_session": totals.last,
    }


def format_dates_short(project: Project) -> str:
    """ "Jul 26 → Jan 27": `format_dates` by month."""

    start = f"{project.start:%b %y}" if project.start else ""
    end = f"{project.end:%b %y}" if project.end else ""
    if start and end:
        return f"{start} → {end}"
    if start:
        return f"from {start}"
    return f"until {end}" if end else ""


def project_cells(db: DBSession, project: Project) -> tables.Cells:
    """Every cell a projects table can show, as markup."""

    customer = db.get(Customer, project.customer_fk) if project.customer_fk else None
    totals = session_totals(db, project_fk=project.id)
    category = escape(category_name(db, project) or "")
    tags = tag_names(db, project)
    name = escape(project.name)
    return {
        "id": str(project.id),
        "name": name,
        # The status in the name, when there's no column for it.
        "name_status": name + (" [dim](archived)[/dim]" if project.archived else ""),
        "customer": escape(customer_name(customer)) if customer else "",
        "category": category,
        "tags": escape(", ".join(tags)),
        "labels": " ".join([category, *(f"#{escape(t)}" for t in tags)]).strip(),
        "rate": format_rate(project.rate),
        "dates": format_dates(project),
        "dates_short": format_dates_short(project),
        "sessions": str(totals.sessions),
        "time": format_duration(totals.time),
        "status": "[dim]archived[/dim]" if project.archived else "",
    }


NAME = tables.col("name", style="green", flex=True)
TIME = tables.col("time", right=True)
# Widest first; see `tables.py`.
LAYOUTS: list[tables.Layout] = [
    [
        tables.ID,
        NAME,
        tables.col("customer", optional=True),
        tables.col("category", style="magenta", optional=True),
        tables.col("tags", style="magenta", optional=True),
        tables.col("rate", right=True, optional=True),
        tables.col("dates", optional=True),
        tables.col("sessions", right=True),
        TIME,
        tables.col("status", optional=True),
    ],
    [
        tables.ID,
        NAME,
        tables.col("customer", optional=True),
        tables.col("labels", style="magenta", flex=True, least=10, optional=True),
        tables.col("rate", right=True, optional=True),
        tables.col("dates_short", "Dates", optional=True),
        TIME,
        tables.col("status", optional=True),
    ],
    [
        tables.ID,
        tables.col("name_status", "Name", style="green", flex=True),
        tables.col("customer", optional=True),
        tables.col("dates_short", "Dates", optional=True),
        TIME,
    ],
    [
        tables.ID,
        tables.col("name_status", "Name", style="green", flex=True),
        tables.col("customer", optional=True),
        TIME,
    ],
    [tables.ID, tables.col("name_status", "Name", style="green", flex=True), TIME],
]


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


def show_project(db: DBSession, project: Project, screen: tui.Screen) -> None:
    from trak import views
    from trak.projects.view import ProjectView

    views.show_in(db, ProjectView, project, screen)


def edit_project(db: DBSession, project: Project, prompter: Prompter) -> str:
    from trak.projects.commands import ask_edits, project_label
    from trak.projects.services import update_project

    return entities.edit_in_place(
        db,
        project,
        prompter,
        ask=ask_edits,
        update=update_project,
        noun="project",
        label=project_label,
    )


def project_listing(db: DBSession) -> browser.Listing[Project, ProjectFilters]:
    return browser.Listing(
        show=lambda project, screen: show_project(db, project, screen),
        edit=lambda project, prompter: edit_project(db, project, prompter),
        noun="project",
        query=lambda filters: query(db, filters),
        cells=lambda project: project_cells(db, project),
        layouts=LAYOUTS,
        to_json=lambda project: project_json(db, project),
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
    fit: bool = True,
) -> Project | None:
    """Browse the projects until the user quits (None), or pick one."""

    return browser.browse(
        project_listing(db),
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
        int | None,
        typer.Option(
            "--per-page",
            min=1,
            max=500,
            help="Projects per page. Default: what fits the terminal; 20 when printed.",
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
            per_page=per_page or browser.PER_PAGE,
        )

        if plain or not commands.is_interactive():
            browser.print_page(project_listing(db), filters)
            return

        entities.run_browser(
            lambda prompter: browse(db, prompter, filters, fit=per_page is None)
        )
