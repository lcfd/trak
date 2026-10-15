"""A bare `trak`: the home, and the commands its Actions pane lists and ranks."""

import typer
from typer.core import TyperCommand, TyperGroup

from trak import tui
from trak.main import home
from trak.sessions import commands

# Top-level groups listed in --help but not in the menu.
NOT_IN_MENU = {"dev"}


def collect_commands(
    group: TyperGroup, ctx: typer.Context, prefix: str = ""
) -> list[tuple[str, TyperCommand]]:
    """Every visible leaf command of `group`, as ("sessions list", command)."""

    found: list[tuple[str, TyperCommand]] = []
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if command is None or command.hidden:
            continue
        if not prefix and name in NOT_IN_MENU:
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


def invoke_with_defaults(
    ctx: typer.Context, command: TyperCommand | TyperGroup, name: str
) -> None:
    """Run `command` under `ctx` as if typed with no arguments."""

    with command.make_context(name, [], parent=ctx) as sub_ctx:
        command.invoke(sub_ctx)


def run_menu(ctx: typer.Context) -> None:
    """
    The home (`main/home.py`): goals, sessions and every command, full screen.
    Without a terminal it prints the help instead. Ctrl-C exits with 130.
    """

    if not commands.is_interactive():
        typer.echo(ctx.get_help())
        return

    assert isinstance(ctx.command, TyperGroup)
    entries = collect_commands(ctx.command, ctx)
    rows = [(path, command.get_short_help_str(limit=60)) for path, command in entries]
    rows.append((home.HELP, "Show every command and option (like --help)."))
    rows.append((home.QUIT, "Leave trak."))
    view = home.Home(ctx, commands=dict(entries), actions=rows)

    try:
        with open_screen() as screen:
            view.loop(screen)
    except KeyboardInterrupt:
        raise typer.Exit(130)


# The terminal, full screen; tests swap it for a fake one.
open_screen = tui.open_screen
