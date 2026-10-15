"""
`trak categories ...` and `trak tags ...`: the same commands for both, made
for a `Kind` by `entity_app`.
"""

from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, forms, output
from trak.base_messages import print_error, print_success, print_warning
from trak.customers.models import Customer
from trak.entities import entity_app
from trak.labels import listing
from trak.labels.listing import LabelFilters, label_json
from trak.labels.services import (
    Kind,
    check_label,
    create_label,
    delete_label,
    labelled,
    session_filter,
    update_label,
)
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import format_duration
from trak.sessions.editing import format_time
from trak.sessions.guided import input_validator
from trak.sessions.services import session_totals


def label_text(row: Any) -> str:
    return f"[magenta]{escape(row.name)}[/magenta]"


def names(rows: list[Any]) -> str:
    return ", ".join(escape(row.name or f"#{row.id}") for row in rows)


def name_validator(db: DBSession, kind: Kind, label_id: int | None = None) -> Any:
    return input_validator(
        lambda text: check_label(db, kind, text.strip(), label_id=label_id)
    )


def print_label(db: DBSession, kind: Kind, row: Any) -> None:
    """The panel of `trak categories|tags show`."""

    totals = session_totals(db, **session_filter(kind, row))
    entities.print_details(
        title=f"{kind.title} #{row.id}",
        rows=[
            ("Name", label_text(row)),
            ("Projects", names(labelled(db, kind, row, Project)) or "[dim]—[/dim]"),
            ("Customers", names(labelled(db, kind, row, Customer)) or "[dim]—[/dim]"),
            ("Sessions", str(totals.sessions)),
            ("Time", format_duration(totals.time)),
            (
                "Last session",
                entities.or_dash(totals.last and format_time(totals.last)),
            ),
        ],
        hint=f'Edit it with "trak {kind.plural} edit {row.id}".',
    )


def ask_edits(db: DBSession, kind: Kind, prompter: Any, row: Any) -> dict[str, Any]:
    """The edit form of a label: its name."""

    def ask_field(changes: dict[str, Any], field: str) -> None:
        changes["name"] = prompter.input(
            "Name",
            value=forms.current(row, changes, "name"),
            validator=name_validator(db, kind, row.id),
        ).strip()

    return forms.ask_changes(
        prompter,
        f"Edit {kind.noun} #{row.id}",
        row,
        rows=lambda changes: [("name", "Name", forms.current(row, changes, "name"))],
        ask_field=ask_field,
    )


def make_app(kind: Kind) -> typer.Typer:
    """The Typer app of `trak <kind.plural>`."""

    noun, plural = kind.noun, kind.plural

    IdArgument = Annotated[
        int | None,
        typer.Argument(
            metavar="ID", help=f"The {noun}. Leave it empty to pick one from the list."
        ),
    ]

    def get_or_pick(db: DBSession, label_id: int | None, verb: str) -> Any:
        done = {"show": "shown", "edit": "edited", "delete": "deleted"}[verb]
        return entities.get_or_pick(
            db,
            kind.model,
            label_id,
            lambda prompter: listing.browse(
                db,
                kind,
                prompter,
                LabelFilters(),
                pick=True,
                title=f"Pick a {noun} to {verb}",
            ),
            noun=noun,
            command=f"trak {plural} {verb}",
            cancelled=f"No {noun} was {done}.",
        )

    def create_command(
        ctx: typer.Context,
        name: Annotated[
            str | None,
            typer.Argument(
                metavar="NAME", help=f"The {noun}'s name. Leave it empty to type it."
            ),
        ] = None,
    ) -> None:
        with DBSession(ctx.obj["DB_ENGINE"]) as db:
            if name is None:
                entities.require_terminal(f"Creating a {noun} without a name")
                name = commands.run_prompts(
                    lambda prompter: prompter.input(
                        "Name",
                        placeholder="e.g. Design",
                        validator=name_validator(db, kind),
                    ),
                    cancelled=f"No {noun} was created.",
                )
            try:
                row = create_label(db, kind, name=name)
            except ValueError as e:
                print_error(title=f"Can't create the {noun}", text=str(e))
                raise typer.Exit(1)

            output.emit(label_json(db, kind, row))
            flag = "--category" if kind.noun == "category" else "--tag"
            print_success(
                title="✨ Create",
                text=(
                    f"{kind.title} #{row.id} {label_text(row)} created.\n\n"
                    f'[dim]Give it to a session with "trak start {flag} '
                    f'{escape(row.name)}".[/dim]'
                ),
            )

    def show_command(ctx: typer.Context, label_id: IdArgument = None) -> None:
        with DBSession(ctx.obj["DB_ENGINE"]) as db:
            row = get_or_pick(db, label_id, "show")
            output.emit(label_json(db, kind, row))
            print_label(db, kind, row)

    def edit_command(
        ctx: typer.Context,
        label_id: IdArgument = None,
        name: Annotated[
            str | None, typer.Option("--name", "-n", help="The name.")
        ] = None,
    ) -> None:
        if name is None:
            entities.require_terminal("Editing without options")

        with DBSession(ctx.obj["DB_ENGINE"]) as db:
            row = get_or_pick(db, label_id, "edit")
            if name is not None:
                changes = forms.effective_changes(row, {"name": name.strip()})
            else:
                changes = commands.run_prompts(
                    lambda prompter: ask_edits(db, kind, prompter, row),
                    cancelled="No changes were saved.",
                )

            entities.save_changes(
                db,
                row,
                changes,
                update=lambda db, row, **changes: update_label(
                    db, kind, row, **changes
                ),
                noun=noun,
                label=label_text,
                to_json=lambda r: label_json(db, kind, r),
            )

    def delete_command(
        ctx: typer.Context,
        label_id: IdArgument = None,
        yes: Annotated[
            bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")
        ] = False,
    ) -> None:
        with DBSession(ctx.obj["DB_ENGINE"]) as db:
            row = get_or_pick(db, label_id, "delete")
            data = label_json(db, kind, row)
            used = data["sessions"] + len(data["projects"]) + len(data["customers"])
            if not yes:
                if not commands.is_interactive():
                    print_error(
                        title=f"Deleting a {noun} needs a confirmation",
                        text="Give --yes to delete it without a terminal.",
                    )
                    raise typer.Exit(1)
                question = f"Delete the {noun} {row.name}?"
                if used:
                    question += f" It comes off {used} sessions, projects, customers."
                confirmed = commands.run_prompts(
                    lambda prompter: prompter.confirm(question, default=False),
                    cancelled=f"No {noun} was deleted.",
                )
                if not confirmed:
                    print_warning(title="Cancelled", text=f"No {noun} was deleted.")
                    raise typer.Exit(1)

            text = f"{kind.title} #{row.id} {label_text(row)} deleted."
            delete_label(db, kind, row)
            output.emit(data)
            print_success(title="🗑️  Delete", text=text)

    show_command.__doc__ = f"Show a {noun}: what has it and the time tracked."
    create_command.__doc__ = f"Create a {noun}."
    edit_command.__doc__ = (
        f"Rename a {noun}. With --name, saves it right away; without, opens the "
        "form (terminal)."
    )
    delete_command.__doc__ = (
        f"Delete a {noun}: it comes off its sessions, projects and customers."
    )
    app = entity_app(plural)
    app.command(name="list", help=f"List {plural} by name.")(
        listing.make_list_command(kind)
    )
    app.command(name="show", help=f"Show a {noun}.")(show_command)
    app.command(name="create", help=f"Create a {noun}.")(create_command)
    app.command(name="edit", help=f"Rename a {noun}.")(edit_command)
    app.command(name="delete", help=f"Delete a {noun}.")(delete_command)
    return app
