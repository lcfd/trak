"""The menu shown by a bare `trak`: pick any command from a filterable list."""

import typer
from rich.console import Console
from rich.text import Text
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession
from typer.core import TyperCommand, TyperGroup

from trak import config
from trak.goals.display import print_reminder
from trak.prompts import PromptCancelled
from trak.sessions import commands
from trak.sessions.guided import Prompter

LOGO = r"""
 _             _
| |_ _ __ __ _| | __
| __| '__/ _` | |/ /
| |_| | | (_| |   <
 \__|_|  \__,_|_|\_\
"""

# The menu entries after the commands: show `trak --help`, and leave.
HELP = "help"
QUIT = "quit"


def print_logo(console: Console) -> None:
    console.print(Text(LOGO.strip("\n"), style="bold green"))
    console.print(f"[dim]v{config.VERSION}[/dim]\n")


def collect_commands(
    group: TyperGroup, ctx: typer.Context, prefix: str = ""
) -> list[tuple[str, TyperCommand]]:
    """Every visible leaf command of `group`, as ("sessions list", command)."""

    found: list[tuple[str, TyperCommand]] = []
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if command is None or command.hidden:
            continue
        path = f"{prefix}{name}"
        if isinstance(command, TyperGroup):
            found += collect_commands(command, ctx, prefix=f"{path} ")
        else:
            found.append((path, command))
    return found


def abbreviation_score(query: str, words: list[str]) -> float | None:
    """
    How well `query` abbreviates `words`: split into chunks, each the start
    of a word, in order ("sl" and "seli" both abbreviate "sessions list").

    Best when the chunks cover every word from the first one; skipping words
    costs more than leaving some out at the end. None if it's no abbreviation.
    """

    def best(qi: int, wi: int, matched: int, last: int) -> float | None:
        if qi == len(query):
            skipped = last + 1 - matched
            trailing = len(words) - last - 1
            return 100 - 20 * skipped + 10 * matched - trailing
        scores = []
        for j in range(wi, len(words)):
            word = words[j]
            length = 0
            while (
                length < len(word)
                and qi + length < len(query)
                and word[length] == query[qi + length]
            ):
                length += 1
            for size in range(length, 0, -1):
                score = best(qi + size, j + 1, matched + 1, j)
                if score is not None:
                    scores.append(score)
        return max(scores, default=None)

    return best(0, 0, 0, -1) if query else None


def is_subsequence(query: str, text: str) -> bool:
    letters = iter(text)
    return all(char in letters for char in query)


def command_score(query: str, path: str, description: str = "") -> float | None:
    """
    How well the menu filter `query` matches a command, best first:
    an abbreviation of its words, a part of its name, its letters in order,
    a part of its description. None if it doesn't match.
    """

    words = path.lower().split()
    compact = "".join(query.lower().split())
    if not compact:
        return 0

    score = abbreviation_score(compact, words)
    if score is not None:
        return score
    if compact in "".join(words):
        return 40
    if is_subsequence(compact, "".join(words)):
        return 20
    if query.strip().lower() in description.lower():
        return 10
    return None


def ask_command(
    prompter: Prompter, entries: list[tuple[str, TyperCommand]]
) -> tuple[str, TyperCommand | None]:
    """The picked command, or (HELP, None) / (QUIT, None) for those entries."""

    rows = [(path, command.get_short_help_str(limit=60)) for path, command in entries]
    rows.append((HELP, "Show every command and option (like --help)."))
    rows.append((QUIT, "Leave trak."))
    width = max(len(path) for path, _ in rows)
    options: list[Option[int]] = [
        {"name": f"{path:<{width}}  {text}", "value": index}
        for index, (path, text) in enumerate(rows)
    ]
    index = prompter.ask(
        "Command",
        options,
        allow_filtering=True,
        rank=lambda text, option: command_score(text, *rows[option["value"]]),
    )
    if index >= len(entries):
        return rows[index][0], None
    return entries[index]


def invoke_with_defaults(
    ctx: typer.Context, command: TyperCommand | TyperGroup, name: str
) -> None:
    """Run `command` under `ctx` as if typed with no arguments."""

    with command.make_context(name, [], parent=ctx) as sub_ctx:
        command.invoke(sub_ctx)


def run_menu(ctx: typer.Context) -> None:
    """
    Let the user pick a command and run it with its defaults. The upcoming
    goals are shown above it, as a reminder.

    Without a terminal it prints the help instead. Going back, or picking
    quit, exits quietly.
    """

    if not commands.is_interactive():
        typer.echo(ctx.get_help())
        return

    assert isinstance(ctx.command, TyperGroup)
    entries = collect_commands(ctx.command, ctx)

    console = Console()
    print_logo(console)
    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        print_reminder(console, db)

    try:
        with commands.make_prompter() as prompter:
            path, command = ask_command(prompter, entries)
    except PromptCancelled:
        return
    except (KeyboardInterrupt, SystemExit):
        # On Ctrl-C rich-toolkit prints "Cancelled." and calls exit().
        raise typer.Exit(130)

    if command is None:
        if path == HELP:
            typer.echo(ctx.get_help())
        return

    invoke_with_defaults(ctx, command, path)
