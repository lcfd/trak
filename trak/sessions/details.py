"""`trak sessions show` (or `trak sessions ID`): every field of a Session."""

from typing import Annotated

import typer
from sqlmodel import Session as DBSession

from trak import entities
from trak.projects.models import Project
from trak.sessions import listing
from trak.sessions.display import elapsed, format_duration, session_customer
from trak.sessions.editing import format_time, row_name
from trak.sessions.models import Category, Session, Tag

IdArgument = Annotated[
    int | None,
    typer.Argument(
        metavar="ID", help="The session. Leave it empty to pick one from the list."
    ),
]


def detail_rows(db: DBSession, session: Session) -> list[tuple[str, str]]:
    customer = session_customer(db, session)
    via_project = customer is not None and session.customer_fk is None
    rows = [
        ("Name", entities.or_dash(session.name)),
        (
            "Project",
            entities.or_dash(
                row_name(db, Project, session.project_fk)
                if session.project_fk
                else None
            ),
        ),
        (
            "Customer",
            entities.or_dash(customer and (customer.name or f"#{customer.id}"))
            + (" [dim](from the project)[/dim]" if via_project else ""),
        ),
    ]
    for model, fk in ((Category, session.category_fk), (Tag, session.tag_fk)):
        rows.append((model.__name__, entities.or_dash(fk and row_name(db, model, fk))))
    rows += [
        ("Start", format_time(session.start)),
        (
            "End",
            format_time(session.end)
            if session.end
            else "[bold green]running[/bold green]",
        ),
        ("Duration", format_duration(elapsed(session))),
    ]
    return rows


def show_command(ctx: typer.Context, session_id: IdArgument = None) -> None:
    """
    Show every field of a session.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        session = listing.get_or_pick(db, session_id, "show")
        entities.print_details(
            title=f"Session #{session.id}",
            rows=detail_rows(db, session),
            hint=f'Edit it with "trak sessions edit {session.id}".',
        )
