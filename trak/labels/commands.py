"""
`trak categories ...` and `trak tags ...`: the same commands for both, made
for a `Kind` by `make_app` (`show` is in view.py).
"""

from collections.abc import Callable
from typing import Annotated, Any

import typer
from rich.markup import escape
from sqlmodel import Session as DBSession

from trak import entities, forms, output
from trak.base_messages import print_error, print_success
from trak.entities import entity_app
from trak.labels import listing
from trak.labels.listing import LabelFilters, label_json
from trak.labels.services import (
    Kind,
    check_label,
    create_label,
    delete_label,
    update_label,
)
from trak.sessions import commands
from trak.sessions.guided import input_validator


def label_text(row: Any) -> str:
    return f"[magenta]{escape(row.name)}[/magenta]"


def name_validator(db: DBSession, kind: Kind, label_id: int | None = None) -> Any:
    return input_validator(
        lambda text: check_label(db, kind, text.strip(), label_id=label_id)
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


def id_argument(kind: Kind) -> Any:
    """The ID argument of `trak <kind.plural> show|edit|delete`."""

    return Annotated[
        int | None,
        typer.Argument(
            metavar="ID",
            help=f"The {kind.noun}. Leave it empty to pick one from the list.",
        ),
    ]


def get_or_pick(db: DBSession, kind: Kind, label_id: int | None, verb: str) -> Any:
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
            title=f"Pick a {kind.noun} to {verb}",
        ),
        noun=kind.noun,
        command=f"trak {kind.plural} {verb}",
        cancelled=f"No {kind.noun} was {done}.",
    )


def make_app(kind: Kind, show_command: Callable[..., None]) -> typer.Typer:
    """
    The Typer app of `trak <kind.plural>`; `show_command` comes from view.py
    (`make_show_command`), which imports this module.
    """

    noun, plural = kind.noun, kind.plural
    IdArgument = id_argument(kind)

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
            row = get_or_pick(db, kind, label_id, "edit")
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
            row = get_or_pick(db, kind, label_id, "delete")
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
                    commands.cancel(f"No {noun} was deleted.")

            text = f"{kind.title} #{row.id} {label_text(row)} deleted."
            delete_label(db, kind, row)
            output.emit(data)
            print_success(title="🗑️  Delete", text=text)

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
