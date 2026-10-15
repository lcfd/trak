"""`trak categories list` / `trak tags list`: browse them, by name."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import browser, entities, output, tables
from trak.customers.models import Customer
from trak.labels.services import Kind, labelled, list_labels, session_filter
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.guided import Prompter
from trak.sessions.listing import ask_name
from trak.sessions.services import session_totals


@dataclass
class LabelFilters:
    name: str = ""
    page: int = 1
    per_page: int = browser.PER_PAGE

    @property
    def active(self) -> bool:
        return bool(self.name)

    def describe(self) -> str:
        return f'name: "{escape(self.name)}"' if self.name else "none"


def label_json(db: DBSession, kind: Kind, row: Any) -> dict[str, Any]:
    """A Category or Tag for `--json`: its fields, what has it, the time tracked."""

    totals = session_totals(db, **session_filter(kind, row))
    return {
        **output.fields(row),
        "projects": [p.name for p in labelled(db, kind, row, Project)],
        "customers": [c.name for c in labelled(db, kind, row, Customer)],
        "sessions": totals.sessions,
        "tracked_seconds": output.seconds(totals.time),
        "last_session": totals.last,
    }


def label_cells(db: DBSession, kind: Kind, row: Any) -> tables.Cells:
    """Every cell a categories or tags table can show, as markup."""

    totals = session_totals(db, **session_filter(kind, row))
    return {
        "id": str(row.id),
        "name": escape(row.name),
        "projects": str(len(labelled(db, kind, row, Project))),
        "customers": str(len(labelled(db, kind, row, Customer))),
        "sessions": str(totals.sessions),
        "time": format_duration(totals.time),
    }


NAME = tables.col("name", style="magenta", flex=True)
TIME = tables.col("time", right=True)
# Widest first; see `tables.py`.
LAYOUTS: list[tables.Layout] = [
    [
        tables.ID,
        NAME,
        tables.col("projects", right=True),
        tables.col("customers", right=True),
        tables.col("sessions", right=True),
        TIME,
    ],
    [tables.ID, NAME, tables.col("sessions", right=True), TIME],
    [tables.ID, NAME, TIME],
]


FILTER_SHORTCUTS: list[browser.Shortcut] = [
    ("/", ("/",), "name", "Search by name"),
]


def show_label(db: DBSession, kind: Kind, row: Any, screen: Any) -> None:
    from trak.labels.commands import print_label

    entities.show_printed(screen, lambda: print_label(db, kind, row))


def edit_label(db: DBSession, kind: Kind, row: Any, prompter: Prompter) -> str:
    from trak.labels.commands import ask_edits, label_text
    from trak.labels.services import update_label

    return entities.edit_in_place(
        db,
        row,
        prompter,
        ask=lambda db, prompter, row: ask_edits(db, kind, prompter, row),
        update=lambda db, row, **changes: update_label(db, kind, row, **changes),
        noun=kind.noun,
        label=label_text,
    )


def label_listing(db: DBSession, kind: Kind) -> browser.Listing[Any, LabelFilters]:
    return browser.Listing(
        show=lambda row, screen: show_label(db, kind, row, screen),
        edit=lambda row, prompter: edit_label(db, kind, row, prompter),
        noun=kind.noun,
        plural_noun=kind.plural,
        query=lambda filters: list_labels(
            db,
            kind,
            name=filters.name or None,
            limit=filters.per_page,
            offset=(filters.page - 1) * filters.per_page,
        ),
        cells=lambda row: label_cells(db, kind, row),
        layouts=LAYOUTS,
        to_json=lambda row: label_json(db, kind, row),
        filter_shortcuts=FILTER_SHORTCUTS,
        ask_filter=lambda prompter, filters, action: ask_name(prompter, filters),  # type: ignore[arg-type]
        clear=lambda filters: LabelFilters(per_page=filters.per_page),
    )


def browse(
    db: DBSession,
    kind: Kind,
    prompter: Prompter,
    filters: LabelFilters,
    pick: bool = False,
    title: str | None = None,
    fit: bool = True,
) -> Any | None:
    """Browse the labels until the user quits (None), or pick one."""

    return browser.browse(
        label_listing(db, kind),
        prompter,
        filters,
        pick=pick,
        title=title or kind.plural.capitalize(),
        fit=fit,
    )


def make_list_command(kind: Kind) -> Callable[..., None]:
    def list_command(
        ctx: typer.Context,
        name: Annotated[
            str | None,
            typer.Option(
                "--name", "-n", help=f"Only the {kind.plural} whose name contains this."
            ),
        ] = None,
        page: Annotated[
            int, typer.Option("--page", min=1, help="The page to show.")
        ] = 1,
        per_page: Annotated[
            int | None,
            typer.Option(
                "--per-page",
                min=1,
                max=500,
                help=f"{kind.plural.capitalize()} per page. "
                "Default: what fits the terminal; 20 when printed.",
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
        with DBSession(ctx.obj["DB_ENGINE"]) as db:
            filters = LabelFilters(
                name=name or "", page=page, per_page=per_page or browser.PER_PAGE
            )
            if plain or not commands.is_interactive():
                browser.print_page(label_listing(db, kind), filters)
                return
            entities.run_browser(
                lambda prompter: browse(
                    db, kind, prompter, filters, fit=per_page is None
                )
            )

    list_command.__doc__ = (
        f"Browse {kind.plural} by name. The option sets the starting filter."
    )
    return list_command
