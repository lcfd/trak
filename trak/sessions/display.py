from datetime import UTC, datetime, timedelta
from typing import Any

from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import output
from trak.customers.models import Customer
from trak.projects.models import Project
from trak.sessions.models import Category, Session, Tag


def format_duration(duration: timedelta) -> str:
    minutes = int(duration.total_seconds()) // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def elapsed(session: Session, now: datetime | None = None) -> timedelta:
    return (session.end or now or datetime.now(UTC)) - session.start


def session_customer(db: DBSession, session: Session) -> Customer | None:
    """The Session's Customer: its own, or else its Project's."""

    customer_fk = session.customer_fk
    if customer_fk is None and session.project_fk is not None:
        project = db.get(Project, session.project_fk)
        customer_fk = project.customer_fk if project else None
    return db.get(Customer, customer_fk) if customer_fk is not None else None


def session_json(
    db: DBSession, session: Session, now: datetime | None = None
) -> dict[str, Any]:
    """
    The Session for `--json`: its fields, the names of its associations
    (`customer` is the effective one, maybe its Project's) and its duration.
    """

    def name_of(model: type, fk: int | None) -> str | None:
        row = db.get(model, fk) if fk is not None else None
        return row.name if row is not None else None

    customer = session_customer(db, session)
    return {
        **output.fields(session),
        "project": name_of(Project, session.project_fk),
        "customer": customer.name if customer else None,
        "customer_from_project": customer is not None and session.customer_fk is None,
        "category": name_of(Category, session.category_fk),
        "tag": name_of(Tag, session.tag_fk),
        "duration_seconds": output.seconds(elapsed(session, now)),
    }


def describe_session(db: DBSession, session: Session) -> str:
    """Plain text: "name · project · customer", whichever are set."""

    project = db.get(Project, session.project_fk) if session.project_fk else None
    customer = session_customer(db, session)
    parts = [
        session.name,
        project.name if project else "",
        (customer.name or f"Customer #{customer.id}") if customer else "",
    ]
    return " · ".join(part for part in parts if part) or f"Session #{session.id}"


def session_label(db: DBSession, session: Session) -> str:
    """`describe_session` as Rich markup, for panels."""

    return f"[green]{escape(describe_session(db, session))}[/green]"


def format_start(moment: datetime, now: datetime | None = None) -> str:
    """ "19:25", with the date in front when it isn't today."""

    local = moment.astimezone()
    today = (now or datetime.now(UTC)).astimezone().date()
    if local.date() == today:
        return f"{local:%H:%M}"
    return f"{local:%a %d %b %Y · %H:%M}"


def _detail_lines(
    db: DBSession, session: Session, rows: list[tuple[str, str]]
) -> list[str]:
    """
    The session as a headline, then its associations and `rows` one per line,
    with the labels aligned.
    """

    project = db.get(Project, session.project_fk) if session.project_fk else None
    customer = session_customer(db, session)
    details = []
    if project:
        details.append(("Project", escape(project.name)))
    if customer:
        via_project = session.customer_fk is None
        details.append(
            (
                "Customer",
                escape(customer.name or f"Customer #{customer.id}")
                + (" [dim](from the project)[/dim]" if via_project else ""),
            )
        )
    for model, fk in ((Category, session.category_fk), (Tag, session.tag_fk)):
        row = db.get(model, fk) if fk is not None else None
        if row is not None:
            details.append((model.__name__, escape(row.name or f"#{fk}")))
    details.extend(rows)

    width = max(len(label) for label, _ in details)
    return [
        f"[bold green]{escape(session.name or f'Session #{session.id}')}[/bold green]",
        "",
        *(f"[dim]{label:<{width}}[/dim]  {value}" for label, value in details),
    ]


def _running_line(others: int, verb: str) -> str:
    sessions = "session is" if others == 1 else "sessions are"
    return f"[dim]{others} other {sessions} {verb}running.[/dim]"


def started_text(db: DBSession, session: Session, running: int = 1) -> str:
    """
    The body of the panel `trak start` prints: the session as a headline, its
    associations one per line, and how to stop it. `running` counts the
    active sessions, this one included.
    """

    lines = [
        *_detail_lines(db, session, [("Started", format_start(session.start))]),
        "",
    ]
    if running > 1:
        lines.append(_running_line(running - 1, ""))
    lines.append('[dim]Stop it with "trak stop".[/dim]')
    return "\n".join(lines)


def stopped_text(db: DBSession, sessions: list[Session], running: int = 0) -> str:
    """
    The body of the panel `trak stop` prints: each stopped session like
    `started_text`, plus when it stopped and how long it lasted, then the
    total when there are more. `running` counts the sessions still active.
    """

    lines = []
    for session in sessions:
        assert session.end is not None
        lines += _detail_lines(
            db,
            session,
            [
                ("Started", format_start(session.start)),
                ("Stopped", format_start(session.end)),
                (
                    "Duration",
                    f"[bold green]{format_duration(elapsed(session))}[/bold green]",
                ),
            ],
        )
        lines.append("")

    if len(sessions) > 1:
        total = sum((elapsed(s) for s in sessions), timedelta())
        lines += [
            f"[bold]Total[/bold]  [bold green]{format_duration(total)}[/bold green]",
            "",
        ]

    if running:
        lines.append(_running_line(running, "still "))
    else:
        lines.append('[dim]Start a new one with "trak start".[/dim]')
    return "\n".join(lines)


def running_text(db: DBSession, sessions: list[Session]) -> str:
    """The body of the panel `trak status` prints: each running session."""

    lines: list[str] = []
    for session in sessions:
        if lines:
            lines.append("")
        lines += _detail_lines(
            db,
            session,
            [
                ("Started", format_start(session.start)),
                (
                    "Running",
                    f"[bold green]{format_duration(elapsed(session))}[/bold green]",
                ),
                ("Id", str(session.id)),
            ],
        )
    lines += ["", '[dim]Stop it with "trak stop".[/dim]']
    return "\n".join(lines)


def created_text(db: DBSession, session: Session) -> str:
    """The body of the panel `trak sessions create` prints."""

    assert session.end is not None
    lines = _detail_lines(
        db,
        session,
        [
            ("Started", format_start(session.start)),
            ("Stopped", format_start(session.end)),
            (
                "Duration",
                f"[bold green]{format_duration(elapsed(session))}[/bold green]",
            ),
        ],
    )
    lines += ["", f'[dim]Change it with "trak sessions edit {session.id}".[/dim]']
    return "\n".join(lines)
