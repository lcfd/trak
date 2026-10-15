from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession

from trak import browser, entities
from trak.base_messages import print_error
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.sessions import commands
from trak.sessions.display import elapsed, format_duration, session_customer
from trak.sessions.guided import Prompter, input_validator
from trak.sessions.models import Session
from trak.sessions.services import list_sessions, local_midnight


@dataclass
class ListFilters:
    project: Project | None = None
    customer: Customer | None = None
    name: str = ""
    since: date | None = None
    until: date | None = None
    page: int = 1
    per_page: int = 20

    @property
    def active(self) -> bool:
        return bool(
            self.project or self.customer or self.name or self.since or self.until
        )

    def describe(self) -> str:
        parts = []
        if self.project:
            parts.append(f"project: {escape(self.project.name)}")
        if self.customer:
            parts.append(f"customer: {escape(customer_name(self.customer))}")
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
        name=filters.name or None,
        start_from=local_midnight(filters.since) if filters.since else None,
        start_until=(
            local_midnight(filters.until + timedelta(days=1)) if filters.until else None
        ),
        limit=filters.per_page,
        offset=(filters.page - 1) * filters.per_page,
    )


def build_table(
    db: DBSession, sessions: list[Session], cursor: int | None = None
) -> Table:
    """The sessions table; the row at `cursor`, if any, is highlighted."""

    table = Table(header_style="bold", show_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name")
    table.add_column("Project", style="green")
    table.add_column("Customer")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Duration", justify="right")

    now = datetime.now(UTC)
    for index, session in enumerate(sessions):
        project = db.get(Project, session.project_fk) if session.project_fk else None
        customer = session_customer(db, session)
        start = session.start.astimezone()
        if session.end is None:
            end = "[bold green]running[/bold green]"
        else:
            end_local = session.end.astimezone()
            # Same day: the date would just repeat the start's.
            end = (
                f"{end_local:%H:%M}"
                if end_local.date() == start.date()
                else f"{end_local:%Y-%m-%d %H:%M}"
            )
        table.add_row(
            str(session.id),
            escape(session.name),
            escape(project.name) if project else "",
            escape(customer.name or "") if customer else "",
            f"{start:%Y-%m-%d %H:%M}",
            end,
            format_duration(elapsed(session, now)),
            style="reverse" if index == cursor else None,
        )
    return table


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
    ("d", ("d",), "date", "Filter by date"),
]


def ask_filter(
    db: DBSession, prompter: Prompter, filters: ListFilters, action: str
) -> ListFilters:
    if action == "project":
        return ask_project(db, prompter, filters)
    if action == "customer":
        return ask_customer(db, prompter, filters)
    if action == "name":
        return ask_name(prompter, filters)
    return ask_dates(prompter, filters)


def session_listing(db: DBSession) -> browser.Listing[Session, ListFilters]:
    return browser.Listing(
        noun="session",
        query=lambda filters: query(db, filters),
        table=lambda sessions, cursor: build_table(db, sessions, cursor),
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
        int, typer.Option("--per-page", min=1, max=500, help="Sessions per page.")
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

        filters = ListFilters(
            project=project,
            customer=customer,
            name=name or "",
            since=since.date() if since else None,
            until=until.date() if until else None,
            page=page,
            per_page=per_page,
        )

        if plain or not commands.is_interactive():
            print_page(db, filters)
            return

        entities.run_browser(lambda prompter: browse(db, prompter, filters))
