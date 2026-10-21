"""
Deleting any entity: `trak <entities> delete [ID] [--yes]`, and `D` in the
home, the list browsers and the `show` views.

Each entity says how with a `Deletion` (in its listing.py): what else goes
with it, for the question, and how. A delete always asks first: a prompt for
the command (or --yes without a terminal), an overlay in full-screen views
(y deletes, any other key keeps it). The views delete with `D` (`d` filters
the sessions by date).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

import typer
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text
from sqlalchemy import Engine
from sqlmodel import Session as DBSession

from trak import output, tui
from trak.base_messages import print_error, print_success
from trak.sessions import commands

R = TypeVar("R")

YesOption = Annotated[
    bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")
]


@dataclass(frozen=True)
class Deletion(Generic[R]):
    """How to delete one kind of entity."""

    model: type
    noun: str
    # What it is, plain text: "website", "Session #12 Landing page".
    describe: Callable[[DBSession, R], str]
    # What else deleting it does, a sentence ("" for nothing).
    consequences: Callable[[DBSession, R], str]
    delete: Callable[[DBSession, R], None]

    def question(self, db: DBSession, row: R) -> str:
        return f"Delete the {self.noun} {self.describe(db, row)}?"


def count(number: int, noun: str, plural: str = "") -> str:
    """ "1 session", "3 sessions"."""

    return f"{number} {noun if number == 1 else plural or noun + 's'}"


def its(counts: list[tuple[int, str]], verbs: tuple[str, str]) -> str:
    """
    "Its 1 goal goes", "Its 2 goals and 1 session go": the rows counted
    (none left out), with the verb that agrees; "" when there are none.
    """

    counted = [(n, noun) for n, noun in counts if n]
    if not counted:
        return ""
    one = len(counted) == 1 and counted[0][0] == 1
    rows = " and ".join(count(n, noun) for n, noun in counted)
    return f"Its {rows} {verbs[0] if one else verbs[1]}"


# The command line.


def delete_row(
    db: DBSession,
    row: R,
    deletion: Deletion[R],
    *,
    yes: bool,
    to_json: Callable[[R], dict[str, Any]],
    label: str,
    delete: Callable[[], None] | None = None,
    consequences: str | None = None,
) -> None:
    """
    `trak <entities> delete`: ask (unless `yes`), delete, say so. With
    --json, the row as it was. `delete` and `consequences` replace the
    deletion's (e.g. `projects delete --with-sessions`).
    """

    noun = deletion.noun
    if consequences is None:
        consequences = deletion.consequences(db, row)
    if not yes:
        if not commands.is_interactive():
            print_error(
                title=f"Deleting a {noun} needs a confirmation",
                text="Give --yes to delete it without a terminal.",
            )
            raise typer.Exit(1)
        question = deletion.question(db, row)
        if consequences:
            question += f" {consequences}"
        confirmed = commands.run_prompts(
            lambda prompter: prompter.confirm(question, default=False),
            cancelled=f"No {noun} was deleted.",
        )
        if not confirmed:
            commands.cancel(f"No {noun} was deleted.")

    data = to_json(row)
    text = f"{noun.capitalize()} #{row.id} {label} deleted."  # type: ignore[attr-defined]
    if consequences:
        text += f"\n\n[dim]{escape(consequences)}[/dim]"
    if delete is not None:
        delete()
    else:
        deletion.delete(db, row)
    output.emit(data)
    print_success(title="🗑️  Delete", text=text)


# Full-screen views.


def confirm(
    screen: tui.Screen,
    back: tui.Frame,
    question: str,
    more: str,
    read_key: Callable[[], str | None] | None = None,
) -> bool:
    """Ask over `back` (the view as it is): True only on y."""

    lines: list[Text] = [Text(question, style="bold")]
    if more:
        lines.append(Text(more))
    lines += [
        Text(),
        Text.assemble(
            ("y", "bold red"),
            (" delete", "dim"),
            ("  ·  ", "bright_black"),
            ("any other key", "bold cyan"),
            (" keep it", "dim"),
        ),
    ]
    modal = Panel(
        Group(*lines),
        title="[bold red]Delete[/bold red]",
        border_style="red",
        padding=(1, 3),
        expand=False,
    )
    while True:
        screen.draw(tui.overlay(screen.console, back, modal))
        key = (read_key or screen.read_key)()
        if key:
            return key in ("y", "Y")


def delete_in_place(
    engine: Engine,
    deletion: Deletion[Any],
    row_id: Any,
    screen: tui.Screen,
    back: tui.Frame,
    read_key: Callable[[], str | None] | None = None,
) -> tuple[bool, str]:
    """
    `D` in a full-screen view: ask over `back`, then delete. Whether it did,
    and what the footer says about it.
    """

    with DBSession(engine) as db:
        row = db.get(deletion.model, row_id)
        if row is None:
            return False, f"[yellow]That {deletion.noun} is gone.[/yellow]"
        question = deletion.question(db, row)
        more = deletion.consequences(db, row)
        if not confirm(screen, back, question, more, read_key):
            return False, f"[dim]No {deletion.noun} was deleted.[/dim]"
        name = deletion.describe(db, row)
        try:
            deletion.delete(db, row)
        except ValueError as e:
            db.rollback()
            return False, f"[red]Can't delete it:[/red] {escape(str(e))}"
    return True, f"[red]Deleted[/red] {escape(name)}"


def delete_from_browser(
    db: DBSession,
    deletion: Deletion[Any],
    row: Any,
    screen: tui.Screen,
    back: tui.Frame,
    read_key: Callable[[], str] | None = None,
) -> str:
    """`D` in a list browser querying with `db`: its read ends first."""

    row_id = row.id
    db.commit()
    _, message = delete_in_place(
        db.get_bind(),  # type: ignore[arg-type]
        deletion,
        row_id,
        screen,
        back,
        read_key,
    )
    return message
