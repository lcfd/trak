"""
`trak categories|tags show` (or `trak categories|tags ID`): a Category or
Tag, full screen, in two panes (`views.py`): what has it and the time
tracked, and its sessions. With --plain, without a terminal or with --json,
it prints the details and exits.
"""

from collections.abc import Callable
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, output, views
from trak.customers.models import Customer
from trak.labels.commands import ask_edits, get_or_pick, id_argument, label_text
from trak.labels.listing import label_json
from trak.labels.services import (
    CATEGORY,
    TAG,
    Kind,
    labelled,
    session_filter,
    update_label,
)
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import describe_session, format_duration
from trak.sessions.editing import format_time
from trak.sessions.services import list_sessions, session_totals


def names(rows: list[Any]) -> str:
    return ", ".join(escape(row.name or f"#{row.id}") for row in rows)


def label_rows(db: DBSession, kind: Kind, row: Any) -> list[tuple[str, str]]:
    """What has the label and the time tracked with it, as Rich markup."""

    totals = session_totals(db, **session_filter(kind, row))
    return [
        ("Name", label_text(row)),
        ("Projects", names(labelled(db, kind, row, Project)) or "[dim]—[/dim]"),
        ("Customers", names(labelled(db, kind, row, Customer)) or "[dim]—[/dim]"),
        ("Sessions", str(totals.sessions)),
        ("Time", format_duration(totals.time)),
        ("Last session", entities.or_dash(totals.last and format_time(totals.last))),
    ]


def print_label(db: DBSession, kind: Kind, row: Any) -> None:
    """The panel of `trak categories|tags show --plain`."""

    entities.print_details(
        title=f"{kind.title} #{row.id}",
        rows=label_rows(db, kind, row),
        hint=f'Edit it with "trak {kind.plural} edit {row.id}".',
    )


class LabelView(views.DetailView):
    """A Category or Tag; `CategoryView` and `TagView` say which."""

    kind: Kind
    listing = "sessions"

    def fill(self, db: DBSession, row: Any) -> None:
        kind = self.kind
        self.headline = row.name
        self.rows = label_rows(db, kind, row)[1:]  # The name is the headline.

        sessions, total = list_sessions(
            db, **session_filter(kind, row), limit=views.SESSIONS
        )
        flag = "--category" if kind is CATEGORY else "--tag"
        self.list.title = f"Sessions ({total})"
        self.list.empty = (
            "No sessions yet.\n\n"
            f'[dim]Give it to one with "trak start {flag} {escape(row.name)}".[/dim]'
        )
        self.list.load(
            db, sessions, describe=lambda s: describe_session(db, s), current=None
        )

    def ask_edits(self, db: DBSession, prompter: Any, row: Any) -> dict[str, Any]:
        return ask_edits(db, self.kind, prompter, row)

    def update(self, db: DBSession, row: Any, **changes: Any) -> Any:
        return update_label(db, self.kind, row, **changes)


class CategoryView(LabelView):
    kind = CATEGORY
    model = CATEGORY.model
    title = "Category"
    noun = "category"


class TagView(LabelView):
    kind = TAG
    model = TAG.model
    title = "Tag"
    noun = "tag"


VIEWS: dict[str, type[LabelView]] = {"category": CategoryView, "tag": TagView}


def make_show_command(kind: Kind) -> Callable[..., None]:
    def show_command(
        ctx: typer.Context,
        label_id: id_argument(kind) = None,  # type: ignore[valid-type]
        plain: Annotated[
            bool,
            typer.Option(
                "--plain",
                help=f"Print the {kind.noun} and exit, instead of the full screen.",
            ),
        ] = False,
    ) -> None:
        engine = ctx.obj["DB_ENGINE"]
        with DBSession(engine) as db:
            row = get_or_pick(db, kind, label_id, "show")
            output.emit(label_json(db, kind, row))
            if plain or not commands.is_interactive():
                print_label(db, kind, row)
                return
            view = VIEWS[kind.noun](engine, row.id)
        views.run(view)

    show_command.__doc__ = (
        f"Show a {kind.noun}: what has it, the time tracked and its sessions."
    )
    return show_command
