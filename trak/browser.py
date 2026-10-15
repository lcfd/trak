"""
A full-screen, paginated browser for any entity (sessions, projects, ...).

Single keys drive it, vim first: h/l pages, g/G first/last, `?` help, q quit.
Each entity brings its own query, table and filter shortcuts (a `Listing`).
When picking, j/k move a highlighted row across pages and Enter returns it.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from math import ceil
from typing import Any, Generic, Protocol, TypeVar

import typer
from rich import get_console, print
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.segment import Segment, Segments
from rich.style import Style
from rich.table import Table
from rich_toolkit._getchar import getchar as rich_toolkit_getchar

from trak import dev_bar, output
from trak.base_messages import print_error, print_info
from trak.prompts import ESC, PromptCancelled, split_escape
from trak.sessions.guided import Prompter


class Filters(Protocol):
    page: int
    per_page: int

    @property
    def active(self) -> bool: ...

    def describe(self) -> str: ...


R = TypeVar("R")
F = TypeVar("F", bound=Filters)

# (keys shown in the help, key codes, action, description). Vim keys first.
Shortcut = tuple[str, tuple[str, ...], str, str]


def pick_shortcuts(noun: str) -> list[Shortcut]:
    """Only when picking a row."""

    return [
        ("j  ↓", ("j", "\x1b[B"), "down", f"Next {noun}"),
        ("k  ↑", ("k", "\x1b[A"), "up", f"Previous {noun}"),
        ("Enter", ("\r", "\n"), "pick", f"Pick the {noun}"),
    ]


PICK_ACTIONS = {"down", "up", "pick"}
PAGE_SHORTCUTS: list[Shortcut] = [
    ("l  →  Ctrl-f", ("l", "\x1b[C", "\x06"), "next", "Next page"),
    ("h  ←  Ctrl-b", ("h", "\x1b[D", "\x02"), "previous", "Previous page"),
    ("g", ("g",), "first", "First page"),
    ("G", ("G",), "last", "Last page"),
]
END_SHORTCUTS: list[Shortcut] = [
    ("x", ("x",), "clear", "Clear filters"),
    ("?", ("?",), "help", "Show these shortcuts"),
    ("q  Esc", ("q", ESC), "quit", "Quit"),
]

FILTER_HINT = (
    "[dim]Type to filter · [bold]Esc[/bold] then [bold]j[/bold]/[bold]k[/bold] "
    "to move · [bold]Enter[/bold] to pick · [bold]Esc[/bold] twice to go back[/dim]"
)


@dataclass
class Listing(Generic[R, F]):
    """What the browser needs to know about one kind of entity."""

    noun: str
    query: Callable[[F], tuple[list[R], int]]
    # The table of a page; the row at the cursor, if any, is highlighted.
    table: Callable[[list[R], int | None], Table]
    # A row for `--json`.
    to_json: Callable[[R], dict[str, Any]]
    # Shortcuts whose action is a filter, asked with `ask_filter`.
    filter_shortcuts: list[Shortcut]
    # Ask the user for the filter of `action`; may raise PromptCancelled.
    ask_filter: Callable[[Prompter, F, str], F]
    # The filters with nothing set, keeping the page size.
    clear: Callable[[F], F]
    # Toggles that don't ask anything, like "show archived": action -> filters.
    toggles: dict[str, Callable[[F], F]] | None = None

    @property
    def plural(self) -> str:
        return f"{self.noun}s"

    def shortcuts(self, pick: bool = False) -> list[Shortcut]:
        return (
            (pick_shortcuts(self.noun) if pick else [])
            + PAGE_SHORTCUTS
            + self.filter_shortcuts
            + END_SHORTCUTS
        )


def count_pages(total: int, per_page: int) -> int:
    return max(1, ceil(total / per_page))


def footer(listing: Listing, filters: Filters, total: int) -> str:
    pages = count_pages(total, filters.per_page)
    noun = listing.noun if total == 1 else listing.plural
    return f"Page {filters.page} of {pages} · {total} {noun}"


def filter_bar(filters: Filters) -> str:
    return f"[bold]Filters:[/bold] [cyan]{filters.describe()}[/cyan]"


# Plain mode: print one page and exit.


def print_page(listing: Listing[R, F], filters: F) -> None:
    """
    Print one page. In JSON mode: {"items", "total", "page", "pages",
    "per_page"}; an empty result is fine, a page past the last isn't.
    """

    rows, total = listing.query(filters)
    pages = count_pages(total, filters.per_page)

    if output.json_mode():
        if total and not rows:
            print_error(
                title="This page doesn't exist",
                text=f"There are {pages} pages of {listing.plural}.",
            )
            raise typer.Exit(1)
        output.emit(
            {
                "items": [listing.to_json(row) for row in rows],
                "total": total,
                "page": filters.page,
                "pages": pages,
                "per_page": filters.per_page,
            }
        )
        return

    if not total:
        print_info(
            title=f"No {listing.plural}",
            text=f"No {listing.noun} matches these filters.",
        )
        return

    if not rows:
        print_error(
            title="This page doesn't exist",
            text=f"There {'is' if pages == 1 else 'are'} {pages} "
            f"page{'s' if pages > 1 else ''} of {listing.plural}.",
        )
        raise typer.Exit(1)

    print(listing.table(rows, None))
    text = footer(listing, filters, total)
    if filters.page < pages:
        text += f" · next: [bold]--page {filters.page + 1}[/bold]"
    print(f"[dim]{text}[/dim]")


# Interactive mode: browse pages and change filters until the user quits.


def getchar() -> str:
    # rich-toolkit's reader, like the prompts: Ctrl-d arrives as a key.
    return rich_toolkit_getchar()


def screen(
    listing: Listing[R, F],
    filters: F,
    rows: list[R],
    total: int,
    title: str,
    cursor: int | None = None,
) -> Group:
    """The browser's page: filters on top, then the table and the page line."""

    parts: list[RenderableType] = [f"[bold]{title}[/bold]", filter_bar(filters), ""]
    if rows:
        parts.append(listing.table(rows, cursor))
        parts.append(
            f"[dim]{footer(listing, filters, total)} · [bold]?[/bold] shortcuts[/dim]"
        )
    else:
        parts.append(
            f"[dim]No {listing.noun} matches these filters · "
            "[bold]?[/bold] shortcuts[/dim]"
        )
    return Group(*parts)


def help_panel(shortcuts: list[Shortcut]) -> Panel:
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="bold cyan", justify="right")
    grid.add_column()
    for keys, _, _, description in shortcuts:
        grid.add_row(keys, description)
    return Panel(
        grid,
        title="[bold]Shortcuts[/bold]",
        subtitle="[dim]any key to close[/dim]",
        padding=(1, 3),
        expand=False,
    )


def overlay(
    console: Console, background: RenderableType, modal: RenderableType
) -> None:
    """Print `modal` centered over a dimmed `background`."""

    width = console.width
    options = console.options.update(width=width)
    back = console.render_lines(background, options, pad=True)
    front = console.render_lines(modal, options.update(width=width - 4), pad=False)
    front_width = max(Segment.get_line_length(line) for line in front)

    height = max(len(back), len(front) + 2)
    back += [[Segment(" " * width)]] * (height - len(back))
    top = (min(height, console.height - 1 - dev_bar.lines()) - len(front)) // 2
    left = (width - front_width) // 2
    dim = Style(dim=True)

    segments: list[Segment] = []
    for row, line in enumerate(back):
        line = list(Segment.apply_style(line, post_style=dim))
        if top <= row < top + len(front):
            modal_line = Segment.adjust_line_length(front[row - top], front_width)
            before, _, after = Segment.divide(line, [left, left + front_width, width])
            line = [*before, *modal_line, *after]
        segments += [*line, Segment.line()]
    console.print(Segments(segments), end="")


def edit_filter(
    listing: Listing[R, F],
    prompter: Prompter,
    filters: F,
    action: str,
    title: str,
) -> F:
    """Ask for one filter right under the filter bar, where the table was."""

    console = get_console()
    dev_bar.clear(console)
    console.print(Group(f"[bold]{title}[/bold]", filter_bar(filters), FILTER_HINT, ""))
    try:
        return listing.ask_filter(prompter, filters, action)
    except PromptCancelled:
        # Going back leaves the filters as they were.
        return filters


def browse(
    listing: Listing[R, F],
    prompter: Prompter,
    filters: F,
    read_key: Callable[[], str] | None = None,
    pick: bool = False,
    title: str | None = None,
) -> R | None:
    """
    Browse the rows until the user quits (None).

    With `pick`, j/k move a highlighted row across pages and Enter returns it.
    """

    read_key = read_key or getchar
    title = title or listing.plural.capitalize()
    console = get_console()
    shortcuts = listing.shortcuts(pick)
    key_actions = {code: action for _, codes, action, _ in shortcuts for code in codes}
    toggles = listing.toggles or {}

    def keys() -> Iterator[str]:
        while True:
            yield from split_escape(read_key())

    pressed = keys()

    def at_page(page: int) -> F:
        return replace(filters, page=page)  # type: ignore[type-var]

    # The browser is driven by single keys: no cursor needed.
    console.show_cursor(False)
    # The highlighted row when picking; -1 means the last one of the page.
    cursor = 0
    try:
        while True:
            rows, total = listing.query(filters)
            pages = count_pages(total, filters.per_page)
            if filters.page > pages:
                filters = at_page(pages)
                rows, total = listing.query(filters)
            if cursor < 0 or cursor >= len(rows):
                cursor = max(0, len(rows) - 1)

            page = screen(
                listing,
                filters,
                rows,
                total,
                title=title,
                cursor=cursor if pick and rows else None,
            )
            dev_bar.clear(console)
            console.print(page)
            console.show_cursor(False)

            # Ignore keys that do nothing here, without redrawing.
            for key in pressed:
                action = key_actions.get(key)
                if action in PICK_ACTIONS and not rows:
                    continue
                at_bottom = cursor == len(rows) - 1
                if action == "down" and at_bottom and filters.page >= pages:
                    continue
                if action == "up" and cursor == 0 and filters.page <= 1:
                    continue
                if action in ("next", "last") and filters.page >= pages:
                    continue
                if action in ("previous", "first") and filters.page <= 1:
                    continue
                if action == "clear" and not filters.active:
                    continue
                if action is not None:
                    break

            if action == "quit":
                return None
            if action == "pick":
                return rows[cursor]
            if action == "help":
                dev_bar.clear(console)
                overlay(console, page, help_panel(shortcuts))
                next(pressed)
            elif action == "down":
                if cursor < len(rows) - 1:
                    cursor += 1
                else:
                    filters, cursor = at_page(filters.page + 1), 0
            elif action == "up":
                if cursor > 0:
                    cursor -= 1
                else:
                    filters, cursor = at_page(filters.page - 1), -1
            elif action == "next":
                filters, cursor = at_page(filters.page + 1), 0
            elif action == "previous":
                filters, cursor = at_page(filters.page - 1), 0
            elif action == "first":
                filters, cursor = at_page(1), 0
            elif action == "last":
                filters, cursor = at_page(pages), 0
            elif action == "clear":
                filters, cursor = listing.clear(filters), 0
            elif action in toggles:
                filters, cursor = toggles[action](filters), 0
            else:
                filters = edit_filter(listing, prompter, filters, action, title)
                cursor = 0
    finally:
        console.show_cursor(True)
