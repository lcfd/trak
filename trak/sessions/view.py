"""
`trak sessions show` (or `trak sessions ID`): a Session, full screen, in two
panes (`views.py`): its details, and the other sessions of its project.

Enter on a session of the project shows it in its place; Esc goes back to
the one before. With --plain, without a terminal or with --json, it prints
the details and exits.
"""

from typing import Annotated, Any

import typer
from sqlmodel import Session as DBSession

from trak import entities, output, tui, views
from trak.labels.links import tags_text
from trak.projects.models import Project
from trak.sessions import commands, listing
from trak.sessions.display import (
    elapsed,
    format_duration,
    session_customer,
    session_json,
)
from trak.sessions.editing import ask_edits, format_time, row_name
from trak.sessions.models import Category, Session
from trak.sessions.services import (
    list_sessions,
    session_totals,
    stop_session,
    update_session,
)

IdArgument = Annotated[
    int | None,
    typer.Argument(
        metavar="ID", help="The session. Leave it empty to pick one from the list."
    ),
]


def session_rows(db: DBSession, session: Session) -> list[tuple[str, str]]:
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
    category = session.category_fk
    rows.append(
        ("Category", entities.or_dash(category and row_name(db, Category, category)))
    )
    rows.append(("Tags", entities.or_dash(tags_text(db, session))))
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


class SessionView(views.DetailView):
    model = Session
    title = "Session"
    noun = "session"
    tab = "Project"
    listing = "project's sessions"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # The sessions shown before this one, for Esc.
        self.history: list[int] = []
        self.running = False

    @property
    def session_id(self) -> int:
        return self.row_id

    def fill(self, db: DBSession, session: Session) -> None:
        self.headline = session.name or f"Session #{session.id}"
        self.running = session.end is None
        self.rows = session_rows(db, session)
        project = db.get(Project, session.project_fk) if session.project_fk else None
        if project is None:
            self.list.title = "Project"
            self.list.empty = (
                "This session has no project.\n\n"
                "[dim]Press [bold]e[/bold] to give it one.[/dim]"
            )
            self.list.load(db, [], current=session.id)
            return
        totals = session_totals(db, project_fk=project.id)
        noun = "session" if totals.sessions == 1 else "sessions"
        time = format_duration(totals.time)
        self.rows.append(
            ("Project time", f"{time} [dim]in {totals.sessions} {noun}[/dim]")
        )
        self.list.title = f"Sessions of {project.name}"
        rows, _ = list_sessions(db, project_fk=project.id, limit=views.SESSIONS)
        # The project is in the title: each row says what's left.
        self.list.load(db, rows, current=session.id)

    def ask_edits(self, db: DBSession, prompter: Any, row: Any) -> dict[str, Any]:
        return ask_edits(db, prompter, row)

    def update(self, db: DBSession, row: Any, **changes: Any) -> Any:
        return update_session(db, row, **changes)

    def open(self, screen: tui.Screen, session_id: int) -> None:
        """Another session of the project: shown in this one's place."""

        if session_id == self.row_id:
            return
        self.history.append(self.row_id)
        self.row_id = session_id
        self.load()

    def back(self) -> bool:
        if not self.history:
            return False
        self.row_id = self.history.pop()
        self.load()
        return True

    def key(self, screen: tui.Screen, key: str) -> bool:
        if key != "s":
            return False
        if not self.running:
            self.message = "[yellow]This session isn't running.[/yellow]"
            return True
        with DBSession(self.engine) as db:
            session = db.get(Session, self.row_id)
            assert session is not None
            stop_session(db, session)
            took = format_duration(elapsed(session))
        self.message = f"[green]Stopped[/green] [dim]· {took}[/dim]"
        self.load()
        return True

    def extra_hints(self) -> list[tuple[str, str]]:
        pairs = [("s", "stop")] if self.running else []
        if self.history:
            pairs.append(("Esc", "back"))
        return pairs

    def extra_help(self) -> list[tuple[str, str]]:
        return [
            ("s", "Stop the session, if running"),
            ("Esc  Ctrl-o", "Back to the session shown before"),
        ]


def show_command(
    ctx: typer.Context,
    session_id: IdArgument = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain", help="Print the session and exit, instead of the full screen."
        ),
    ] = False,
) -> None:
    """
    Show a session: every field, and the other sessions of its project.
    """

    engine = ctx.obj["DB_ENGINE"]
    with DBSession(engine) as db:
        session = listing.get_or_pick(db, session_id, "show")
        output.emit(session_json(db, session))
        if plain or not commands.is_interactive():
            entities.print_details(
                title=f"Session #{session.id}",
                rows=session_rows(db, session),
                hint=f'Edit it with "trak sessions edit {session.id}".',
            )
            return
        assert session.id is not None
        view = SessionView(engine, session.id)
    views.run(view)
