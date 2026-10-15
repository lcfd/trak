from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

import typer
from rich.markup import escape
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import browser, entities, tables, tui
from trak.base_messages import print_error
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.labels.links import category_name, tag_names
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.sessions import commands
from trak.sessions.display import (
    elapsed,
    format_duration,
    session_customer,
    session_json,
)
from trak.sessions.guided import Prompter, input_validator
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import list_sessions, local_midnight


@dataclass
class ListFilters:
    project: Project | None = None
    customer: Customer | None = None
    category: Category | None = None
    tag: Tag | None = None
    name: str = ""
    since: date | None = None
    until: date | None = None
    page: int = 1
    per_page: int = browser.PER_PAGE

    @property
    def active(self) -> bool:
        return bool(
            self.project
            or self.customer
            or self.category
            or self.tag
            or self.name
            or self.since
            or self.until
        )

    def describe(self) -> str:
        parts = []
        if self.project:
            parts.append(f"project: {escape(self.project.name)}")
        if self.customer:
            parts.append(f"customer: {escape(customer_name(self.customer))}")
        if self.category:
            parts.append(f"category: {escape(self.category.name)}")
        if self.tag:
            parts.append(f"tag: {escape(self.tag.name)}")
        if self.name:
            parts.append(f'name: "{escape(self.name)}"')
        if self.since and self.since == self.until:
            parts.append(f"date: {self.since}")
        elif self.since and self.until:
            parts.append(f"from {self.since} to {self.until}")
        elif self.since:
            parts.append(f"from {self.since}")
        elif self.until:
            parts.append(f"until {self.until}")
        return " · ".join(parts) or "none"


def customer_name(customer: Customer) -> str:
    return customer.name or f"Customer #{customer.id}"


def query(db: DBSession, filters: ListFilters) -> tuple[list[Session], int]:
    return list_sessions(
        db,
        project_fk=filters.project.id if filters.project else None,
        customer_fk=filters.customer.id if filters.customer else None,
        category_fk=filters.category.id if filters.category else None,
        tag_fk=filters.tag.id if filters.tag else None,
        name=filters.name or None,
        start_from=local_midnight(filters.since) if filters.since else None,
        start_until=(
            local_midnight(filters.until + timedelta(days=1)) if filters.until else None
        ),
        limit=filters.per_page,
        offset=(filters.page - 1) * filters.per_page,
    )


def session_cells(db: DBSession, session: Session) -> tables.Cells:
    """Every cell a sessions table can show, as markup."""

    now = datetime.now(UTC)
    project = db.get(Project, session.project_fk) if session.project_fk else None
    customer = session_customer(db, session)
    start = session.start.astimezone()
    day = tables.short_day(start.date(), now.astimezone().date())
    if session.end is None:
        end = "[bold green]running[/bold green]"
        until = "[bold green]now[/bold green]"
    else:
        end_local = session.end.astimezone()
        days = (end_local.date() - start.date()).days
        # Same day: the date would just repeat the start's.
        end = f"{end_local:%H:%M}" if not days else f"{end_local:%Y-%m-%d %H:%M}"
        until = f"{end_local:%H:%M}" + (f" [dim](+{days})[/dim]" if days else "")

    name = escape(session.name)
    project_name = escape(project.name) if project else ""
    customer_name = escape(customer.name or "") if customer else ""
    category = escape(category_name(db, session) or "")
    tags = tag_names(db, session)
    labels = " ".join([category, *(f"#{escape(tag)}" for tag in tags)]).strip()
    return {
        "id": str(session.id),
        "name": name,
        "project": f"[green]{project_name}[/green]" if project else "",
        "customer": customer_name,
        "project_customer": " ".join(
            part
            for part in (
                f"[green]{project_name}[/green]" if project else "",
                f"[dim]· {customer_name}[/dim]" if customer_name else "",
            )
            if part
        ),
        "category": category,
        "tags": escape(", ".join(tags)),
        "labels": labels,
        "session": " [dim]·[/dim] ".join(
            part
            for part in (name, f"[green]{project_name}[/green]" if project else "")
            if part
        ),
        "start": f"{start:%Y-%m-%d %H:%M}",
        "end": end,
        "when": f"{day} {start:%H:%M}–{until}",
        "since": f"{day} {start:%H:%M}",
        "duration": format_duration(elapsed(session, now)),
    }


DURATION = tables.col("duration", right=True)
# Widest first; see `tables.py`.
LAYOUTS: list[tables.Layout] = [
    [
        tables.ID,
        tables.col("name", flex=True),
        tables.col("project", optional=True),
        tables.col("customer", optional=True),
        tables.col("category", style="magenta", optional=True),
        tables.col("tags", style="magenta", optional=True),
        tables.col("start"),
        tables.col("end"),
        DURATION,
    ],
    [
        tables.ID,
        tables.col("name", flex=True),
        tables.col("project_customer", "Project", optional=True),
        tables.col("labels", style="magenta", flex=True, least=10, optional=True),
        tables.col("when"),
        DURATION,
    ],
    [
        tables.ID,
        tables.col("name", flex=True),
        tables.col("project", optional=True),
        tables.col("labels", style="magenta", flex=True, least=10, optional=True),
        tables.col("when"),
        DURATION,
    ],
    [
        tables.ID,
        tables.col("name", flex=True),
        tables.col("project", optional=True),
        tables.col("when"),
        DURATION,
    ],
    [
        tables.ID,
        tables.col("session", flex=True),
        tables.col("since", "Start"),
        DURATION,
    ],
    [tables.ID, tables.col("session", flex=True), DURATION],
]


# Plain mode: print one page and exit.


def print_page(db: DBSession, filters: ListFilters) -> None:
    browser.print_page(session_listing(db), filters)


# Interactive mode: browse pages and change filters until the user quits.


def parse_day(value: str) -> date | None:
    """Empty means no day. Accepts "YYYY-MM-DD", "today" and "yesterday"."""

    value = value.strip().lower()
    if not value:
        return None
    today = datetime.now().date()
    if value == "today":
        return today
    if value == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('use "YYYY-MM-DD", "today" or "yesterday"') from None


def _required_day(value: str) -> date:
    day = parse_day(value)
    if day is None:
        raise ValueError("a day is required")
    return day


day_validator = input_validator(parse_day)
required_day_validator = input_validator(_required_day)
DAY_PLACEHOLDER = 'YYYY-MM-DD, "today" or "yesterday"'


def ask_project(db: DBSession, prompter: Prompter, filters: ListFilters) -> ListFilters:
    projects = get_projects(db, archived=True)
    options: list[Option[Project | None]] = [{"name": "Any project", "value": None}]
    options += [
        {"name": p.name + (" (archived)" if p.archived else ""), "value": p}
        for p in projects
    ]
    project = prompter.ask("Project", options, allow_filtering=True)
    return replace(filters, project=project, page=1)


def ask_customer(
    db: DBSession, prompter: Prompter, filters: ListFilters
) -> ListFilters:
    options: list[Option[Customer | None]] = [{"name": "Any customer", "value": None}]
    options += [{"name": customer_name(c), "value": c} for c in get_customers(db)]
    customer = prompter.ask("Customer", options, allow_filtering=True)
    return replace(filters, customer=customer, page=1)


def ask_label(
    db: DBSession, prompter: Prompter, filters: ListFilters, model: type
) -> ListFilters:
    rows = list(db.exec(select(model).order_by(model.name)))  # type: ignore[attr-defined]
    noun = model.__name__.lower()
    options: list[Option[Any]] = [{"name": f"Any {noun}", "value": None}]
    options += [{"name": row.name, "value": row} for row in rows]
    row = prompter.ask(model.__name__, options, allow_filtering=True)
    return replace(filters, page=1, **{noun: row})


def ask_name(prompter: Prompter, filters: ListFilters) -> ListFilters:
    name = prompter.input(
        "Name", value=filters.name, placeholder="part of the name, empty for any"
    )
    return replace(filters, name=name.strip(), page=1)


def ask_dates(prompter: Prompter, filters: ListFilters) -> ListFilters:
    options: list[Option[str]] = [
        {"name": "A single day", "value": "day"},
        {"name": "A range of days", "value": "range"},
        {"name": "Any date", "value": "any"},
    ]
    kind = prompter.ask("Date", options)

    if kind == "any":
        return replace(filters, since=None, until=None, page=1)

    if kind == "day":
        day = _required_day(
            prompter.input(
                "Day", placeholder=DAY_PLACEHOLDER, validator=required_day_validator
            )
        )
        return replace(filters, since=day, until=day, page=1)

    since = parse_day(
        prompter.input(
            "From",
            placeholder=DAY_PLACEHOLDER + ", empty for no limit",
            validator=day_validator,
        )
    )
    until = parse_day(
        prompter.input(
            "To",
            placeholder=DAY_PLACEHOLDER + ", empty for no limit",
            validator=day_validator,
        )
    )
    if since and until and since > until:
        since, until = until, since
    return replace(filters, since=since, until=until, page=1)


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("/", ("/",), "name", "Search by name"),
    ("p", ("p",), "project", "Filter by project"),
    ("c", ("c",), "customer", "Filter by customer"),
    ("C", ("C",), "category", "Filter by category"),
    ("t", ("t",), "tag", "Filter by tag"),
    ("d", ("d",), "date", "Filter by date"),
]


def ask_filter(
    db: DBSession, prompter: Prompter, filters: ListFilters, action: str
) -> ListFilters:
    if action == "project":
        return ask_project(db, prompter, filters)
    if action == "customer":
        return ask_customer(db, prompter, filters)
    if action in ("category", "tag"):
        return ask_label(
            db, prompter, filters, Category if action == "category" else Tag
        )
    if action == "name":
        return ask_name(prompter, filters)
    return ask_dates(prompter, filters)


def show_session(db: DBSession, session: Session, screen: tui.Screen) -> None:
    from trak import views
    from trak.sessions.view import SessionView

    views.show_in(db, SessionView, session, screen)


def edit_session(db: DBSession, session: Session, prompter: Prompter) -> str:
    from trak.sessions.display import session_label
    from trak.sessions.editing import ask_edits
    from trak.sessions.services import update_session

    return entities.edit_in_place(
        db,
        session,
        prompter,
        ask=ask_edits,
        update=update_session,
        noun="session",
        label=lambda s: session_label(db, s),
    )


def session_listing(db: DBSession) -> browser.Listing[Session, ListFilters]:
    return browser.Listing(
        show=lambda session, screen: show_session(db, session, screen),
        edit=lambda session, prompter: edit_session(db, session, prompter),
        noun="session",
        query=lambda filters: query(db, filters),
        cells=lambda session: session_cells(db, session),
        layouts=LAYOUTS,
        to_json=lambda session: session_json(db, session),
        filter_shortcuts=FILTER_SHORTCUTS,
        ask_filter=lambda prompter, filters, action: ask_filter(
            db, prompter, filters, action
        ),
        clear=lambda filters: ListFilters(per_page=filters.per_page),
    )


# Every shortcut of the browser, when not picking.
SHORTCUTS = browser.PAGE_SHORTCUTS + FILTER_SHORTCUTS + browser.END_SHORTCUTS


def browse(
    db: DBSession,
    prompter: Prompter,
    filters: ListFilters,
    read_key: Callable[[], str] | None = None,
    pick: bool = False,
    title: str = "Sessions",
    fit: bool = True,
) -> Session | None:
    """
    Browse the sessions until the user quits (None).

    With `pick`, j/k move a highlighted row across pages and Enter returns
    its session.
    """

    return browser.browse(
        session_listing(db),
        prompter,
        filters,
        read_key=read_key,
        pick=pick,
        title=title,
        fit=fit,
    )


def get_or_pick(db: DBSession, session_id: int | None, verb: str) -> Session:
    """The session with `session_id`, or the one the user picks to `verb`."""

    return entities.get_or_pick(
        db,
        Session,
        session_id,
        lambda prompter: browse(
            db, prompter, ListFilters(), pick=True, title=f"Pick a session to {verb}"
        ),
        noun="session",
        command=f"trak sessions {verb}",
        cancelled=f"No session was {'shown' if verb == 'show' else 'edited'}.",
    )


def list_command(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Only the sessions of this project."),
    ] = None,
    customer_name_: Annotated[
        str | None,
        typer.Option(
            "--customer",
            "-c",
            help="Only the sessions of this customer, directly or through a project.",
        ),
    ] = None,
    category_name_: Annotated[
        str | None,
        typer.Option("--category", help="Only the sessions of this category."),
    ] = None,
    tag_name: Annotated[
        str | None,
        typer.Option("--tag", "-t", help="Only the sessions with this tag."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name", "-n", help="Only the sessions whose name contains this."
        ),
    ] = None,
    day: Annotated[
        datetime | None,
        typer.Option(
            "--date",
            "-d",
            formats=["%Y-%m-%d"],
            metavar="YYYY-MM-DD",
            help="Only the sessions started on this day.",
        ),
    ] = None,
    since: Annotated[
        datetime | None,
        typer.Option(
            "--from",
            formats=["%Y-%m-%d"],
            metavar="YYYY-MM-DD",
            help="Only the sessions started on this day or later.",
        ),
    ] = None,
    until: Annotated[
        datetime | None,
        typer.Option(
            "--to",
            formats=["%Y-%m-%d"],
            metavar="YYYY-MM-DD",
            help="Only the sessions started on this day or earlier.",
        ),
    ] = None,
    page: Annotated[int, typer.Option("--page", min=1, help="The page to show.")] = 1,
    per_page: Annotated[
        int | None,
        typer.Option(
            "--per-page",
            min=1,
            max=500,
            help="Sessions per page. Default: what fits the terminal; 20 when printed.",
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
    Browse sessions, newest first. The options set the starting filters.
    """

    if day is not None:
        if since is not None or until is not None:
            print_error(
                title="Conflicting dates", text="Use --date, or --from/--to, not both."
            )
            raise typer.Exit(1)
        since = until = day

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = commands.find_project(db, project_name, archived=True)
            if project is None:
                raise typer.Exit(1)

        customer = None
        if customer_name_ is not None:
            customer = commands.find_customer(db, customer_name_)
            if customer is None:
                raise typer.Exit(1)

        labels: dict[str, Any] = {}
        for key, model, value in (
            ("category", Category, category_name_),
            ("tag", Tag, tag_name),
        ):
            if value is not None:
                labels[key] = commands.find_row(db, model, value.strip(), key)
                if labels[key] is None:
                    raise typer.Exit(1)

        filters = ListFilters(
            project=project,
            customer=customer,
            **labels,
            name=name or "",
            since=since.date() if since else None,
            until=until.date() if until else None,
            page=page,
            per_page=per_page or browser.PER_PAGE,
        )

        if plain or not commands.is_interactive():
            print_page(db, filters)
            return

        entities.run_browser(
            lambda prompter: browse(db, prompter, filters, fit=per_page is None)
        )
