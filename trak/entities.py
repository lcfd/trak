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
from rich.markup import escape
from sqlmodel import Session as DBSession
from typer.core import TyperGroup

from trak.base_messages import print_error, print_info, print_warning
from trak.main.menu import invoke_with_defaults
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
