"""
What every entity group (`trak sessions`, `trak projects`, ...) shares.

- `trak <entities>` alone lists them.
- `trak <entities> <ID>` shows one: it's `trak <entities> show <ID>`.
- `show` and `edit` take an optional ID; without it the user picks the row
  in the list browser.
"""

from collections.abc import Callable
from typing import Any, TypeVar

import click
import typer
from rich.console import Console
from rich.markup import escape
from sqlmodel import Session as DBSession
from typer.core import TyperGroup

from trak import dev_bar, output
from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.main.menu import invoke_with_defaults
from trak.prompts import PromptCancelled
from trak.sessions import commands
from trak.sessions.guided import Prompter

R = TypeVar("R")


class EntityGroup(TyperGroup):
    """A group where a number in place of the command means `show <number>`."""

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0].isdigit():
            args = ["show", *args]
        return super().resolve_command(ctx, args)


def entity_app(plural: str) -> typer.Typer:
    """The Typer app of `trak <plural>`: alone, it runs `list`."""

    app = typer.Typer(
        cls=EntityGroup,
        subcommand_metavar="ID | COMMAND [ARGS]...",
        help=(
            f"Work with your {plural}. Alone, it lists them; "
            f'"trak {plural} ID" shows one.'
        ),
    )

    @app.callback(invoke_without_command=True)
    def callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            assert isinstance(ctx.command, TyperGroup)
            command = ctx.command.get_command(ctx, "list")
            assert command is not None
            invoke_with_defaults(ctx, command, "list")

    return app


def require_terminal(what: str) -> None:
    if not commands.is_interactive():
        print_error(
            title=f"{what} needs a terminal",
            text="Run it in an interactive terminal.",
        )
        raise typer.Exit(1)


def get_or_pick(
    db: DBSession,
    model: type[R],
    entity_id: int | None,
    pick: Callable[[Prompter], R | None],
    noun: str,
    command: str,
    cancelled: str,
) -> R:
    """
    The row with `entity_id`, or the one the user picks in the browser.

    Exits with 1 if it doesn't exist or the user quits the browser.
    `command` is how to pick it instead, for the error.
    """

    if entity_id is not None:
        row = db.get(model, entity_id)
        if row is None:
            print_error(
                title=f"This {noun} doesn't exist",
                text=(
                    f"There's no {noun} #{entity_id}.\n\n"
                    f'Run "{command}" to pick one from the list.'
                ),
            )
            raise typer.Exit(1)
        return row

    require_terminal("Picking")
    row = commands.run_prompts(pick, cancelled=cancelled)
    if row is None:
        print_warning(title="Cancelled", text=cancelled)
        raise typer.Exit(1)
    return row


def save_changes(
    db: DBSession,
    row: R,
    changes: dict[str, Any],
    *,
    update: Callable[..., R],
    noun: str,
    label: Callable[[R], str],
    to_json: Callable[[R], dict[str, Any]],
) -> None:
    """
    Save the `changes` to `row` with `update(db, row, **changes)` and report
    it: "Nothing changed", the error (exit 1), or "saved". With --json, the
    row as it is now.
    """

    if not changes:
        output.emit(to_json(row))
        print_info(title="Nothing changed", text=label(row))
        return

    try:
        row = update(db, row, **changes)
    except ValueError as e:
        print_error(title=f"Can't save the {noun}", text=str(e))
        raise typer.Exit(1)

    output.emit(to_json(row))
    print_success(
        title="✏️  Edit",
        text=f"{noun.capitalize()} #{row.id} {label(row)} saved.",  # type: ignore[attr-defined]
    )


def run_browser(browse: Callable[[Prompter], Any]) -> None:
    try:
        commands.run_prompts(browse)
    except typer.Exit as e:
        # Ctrl-C is a normal way to leave a browser.
        if e.exit_code != 130:
            raise


def print_details(title: str, rows: list[tuple[str, str]], hint: str = "") -> None:
    """A panel of "label  value" lines; values are Rich markup."""

    width = max(len(label) for label, _ in rows)
    lines = [f"[bold]{escape(label):<{width}}[/bold]  {value}" for label, value in rows]
    if hint:
        lines += ["", f"[dim]{hint}[/dim]"]
    print_info(title=title, text="\n".join(lines))


def or_dash(value: Any) -> str:
    return escape(str(value)) if value not in (None, "") else "[dim]—[/dim]"


def show_printed(screen: Any, show: Callable[[], None]) -> None:
    """
    Print a `show` panel from a full-screen browser: on the normal screen,
    until a key brings the browser back.
    """

    with screen.suspended():
        dev_bar.clear(Console())
        show()
        Console().print("[dim]Press any key to go back.[/dim]")
        while screen.read_key() is None:
            pass


def edit_in_place(
    db: DBSession,
    row: R,
    prompter: Prompter,
    *,
    ask: Callable[[DBSession, Prompter, R], dict[str, Any]],
    update: Callable[..., R],
    noun: str,
    label: Callable[[R], str],
) -> str:
    """
    The edit form of `row` from a browser, saved like `save_changes`: what
    the browser's footer says about it.
    """

    try:
        changes = ask(db, prompter, row)
    except PromptCancelled:
        return "[dim]No changes were saved.[/dim]"
    if not changes:
        return "[dim]Nothing changed.[/dim]"
    try:
        row = update(db, row, **changes)
    except ValueError as e:
        db.rollback()
        return f"[red]Can't save the {noun}:[/red] {escape(str(e))}"
    return f"[green]Saved[/green] {label(row)}"
