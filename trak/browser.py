"""
A full-screen, paginated browser for any entity (sessions, projects, ...):
the whole terminal, as many rows a page as it fits (see `tui.py`).

Single keys drive it, vim first: j/k move a highlighted row (across pages),
h/l pages, g/G first/last, `?` help, q quit. Each entity brings its own
query, table and filter shortcuts (a `Listing`). Enter shows the row (`e`
edits it, `y` copies its id) on the same screen; when picking, Enter returns
it instead.

Holding a key down stays smooth: a page is queried and its table built once
(moving the cursor only restyles a row), and every key already typed is
handled before the next frame is drawn.
"""

from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from math import ceil
from typing import Any, Generic, Protocol, TypeVar

import typer
from rich import get_console, print
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich_toolkit._getchar import getchar as rich_toolkit_getchar

from trak import clipboard, output, tables, tui
from trak.base_messages import print_error, print_info
from trak.prompts import ESC, PromptCancelled
from trak.sessions.guided import Prompter


class Filters(Protocol):
    page: int
    per_page: int

    @property
    def active(self) -> bool: ...

    def describe(self) -> str: ...


R = TypeVar("R")
F = TypeVar("F", bound=Filters)

# Rows a printed page has (`--plain`, `--json`) unless --per-page says otherwise.
PER_PAGE = 20

# (keys shown in the help, key codes, action, description). Vim keys first.
Shortcut = tuple[str, tuple[str, ...], str, str]


def row_shortcuts(
    noun: str, pick: bool, show: bool = True, edit: bool = True
) -> list[Shortcut]:
    """What acts on the highlighted row: Enter picks it, or shows it."""

    shortcuts: list[Shortcut] = [
        ("j  ↓", ("j", "\x1b[B"), "down", f"Next {noun}"),
        ("k  ↑", ("k", "\x1b[A"), "up", f"Previous {noun}"),
    ]
    if pick:
        shortcuts.append(("Enter", ("\r", "\n"), "pick", f"Pick the {noun}"))
    elif show:
        shortcuts.append(("Enter", ("\r", "\n"), "open", f"Show the {noun}"))
    if edit and not pick:
        shortcuts.append(("e", ("e",), "edit", f"Edit the {noun}"))
    shortcuts.append(("y", ("y",), "copy", f"Copy the {noun}'s id"))
    return shortcuts


# Actions on the highlighted row: nothing to do without rows.
ROW_ACTIONS = {"down", "up", "pick", "open", "edit", "copy"}
PAGE_SHORTCUTS: list[Shortcut] = [
    ("l  →  Ctrl-f", ("l", "\x1b[C", "\x06"), "next", "Next page"),
    ("h  ←  Ctrl-b", ("h", "\x1b[D", "\x02"), "previous", "Previous page"),
    ("g", ("g",), "first", "First row"),
    ("G", ("G",), "last", "Last row"),
]
END_SHORTCUTS: list[Shortcut] = [
    ("x", ("x",), "clear", "Clear filters"),
    ("?", ("?",), "help", "Show these shortcuts"),
    ("q  Esc", ("q", ESC), "quit", "Quit"),
]


@dataclass
class Listing(Generic[R, F]):
    """What the browser needs to know about one kind of entity."""

    noun: str
    query: Callable[[F], tuple[list[R], int]]
    # A row's cells (markup by key), worked out once for every layout.
    cells: Callable[[R], tables.Cells]
    # The table's layouts, widest first (see `tables.py`).
    layouts: Sequence[tables.Layout]
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
    # When it isn't the noun and an "s".
    plural_noun: str = ""
    # Enter on a row (not picking): show it on the same screen.
    show: Callable[[R, tui.Screen], None] | None = None
    # `e` on a row: edit it on the same screen; returns what the footer says.
    edit: Callable[[R, Prompter], str] | None = None

    @property
    def plural(self) -> str:
        return self.plural_noun or f"{self.noun}s"

    def shortcuts(self, pick: bool = False) -> list[Shortcut]:
        return (
            row_shortcuts(
                self.noun, pick, show=self.show is not None, edit=self.edit is not None
            )
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

    console = get_console()
    print(
        tables.fit(
            console, listing.layouts, [listing.cells(r) for r in rows], console.width
        )
    )
    text = footer(listing, filters, total)
    if filters.page < pages:
        text += f" · next: [bold]--page {filters.page + 1}[/bold]"
    print(f"[dim]{text}[/dim]")


# Interactive mode: browse pages and change filters until the user quits.

# What `getchar` returns when the terminal was resized: draw again.
RESIZE = ""


def getchar() -> str:
    """The next keys typed on the open screen (RESIZE on a resize)."""

    if tui._open:
        return tui._open[-1].read_key() or RESIZE
    # rich-toolkit's reader, like the prompts: Ctrl-d arrives as a key.
    return rich_toolkit_getchar()


def rows_that_fit(console: Console, listing: Listing, width: int, height: int) -> int:
    """How many rows a page can have on a terminal of `width` x `height`."""

    inner_width, inner_height = tui.body_size(width, height)
    options = console.options.update(width=inner_width)
    empty = tables.fit(console, listing.layouts, [], inner_width)
    header = len(console.render_lines(empty, options))
    # The filter bar and a blank line above the table.
    return max(1, inner_height - 2 - header)


def highlight(table: Table, cursor: int | None) -> Table:
    """`table` with only the row at `cursor` highlighted."""

    for index, row in enumerate(table.rows):
        row.style = "reverse" if index == cursor else None
    return table


def screen(
    console: Console,
    width: int,
    listing: Listing[R, F],
    filters: F,
    rows: list[R],
    cursor: int | None = None,
    table: Table | None = None,
) -> Group:
    """
    The browser's page, `width` wide: the filter bar, then the table (`table`,
    already fit to `width`, or built now).
    """

    parts: list[RenderableType] = [filter_bar(filters), ""]
    if rows:
        if table is None:
            cells = [listing.cells(row) for row in rows]
            table = tables.fit(console, listing.layouts, cells, width)
        parts.append(highlight(table, cursor))
    else:
        parts.append(f"[dim]No {listing.noun} matches these filters.[/dim]")
    return Group(*parts)


def hints(listing: Listing, pick: bool) -> list[tuple[str, str]]:
    pairs = [("j/k", "move")]
    if pick:
        pairs.append(("Enter", "pick"))
    else:
        if listing.show is not None:
            pairs.append(("Enter", "show"))
        if listing.edit is not None:
            pairs.append(("e", "edit"))
    pairs += [("y", f"copy {listing.noun} id"), ("h/l", "pages")]
    pairs += [
        (keys.split()[0], description.lower())
        for keys, _, _, description in listing.filter_shortcuts
    ]
    return [*pairs, ("?", "shortcuts"), ("q", "quit")]


def frame(
    console: Console,
    size: tuple[int, int],
    listing: Listing[R, F],
    filters: F,
    rows: list[R],
    total: int,
    title: str,
    cursor: int | None,
    pick: bool,
    message: str = "",
    table: Table | None = None,
) -> tui.Frame:
    width, height = size
    inner_width, _ = tui.body_size(width, height)
    return tui.page(
        console,
        width,
        height,
        title=title,
        body=screen(console, inner_width, listing, filters, rows, cursor, table),
        subtitle=footer(listing, filters, total),
        footer=(
            Text.from_markup(f" {message}")
            if message
            else tui.hints(hints(listing, pick))
        ),
    )


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


def edit_filter(
    listing: Listing[R, F],
    prompter: Prompter,
    filters: F,
    action: str,
    title: str,
) -> F:
    """Ask for one filter (full screen, like every prompt)."""

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
    fit: bool = True,
) -> R | None:
    """
    Browse the rows until the user quits (None), full screen. j/k move a
    highlighted row across pages; Enter shows it (`listing.show`), or with
    `pick` returns it.

    With `fit`, a page has as many rows as the terminal fits, again on every
    resize (keeping the row at the cursor in view); otherwise
    `filters.per_page`.
    """

    read_key = read_key or getchar
    title = title or listing.plural.capitalize()
    shortcuts = listing.shortcuts(pick)
    key_actions = {code: action for _, codes, action, _ in shortcuts for code in codes}
    toggles = listing.toggles or {}

    # The keys typed and not handled yet: all of them are, before drawing.
    pending: deque[str] = deque()

    def next_key() -> str:
        if not pending:
            pending.extend(tui.split_keys(read_key()) or [RESIZE])
        return pending.popleft()

    def at_page(page: int) -> F:
        return replace(filters, page=page)  # type: ignore[type-var]

    # The page last queried, and its table fit to the width: (key, value).
    queried: tuple[Any, tuple[list[R], int]] | None = None
    fitted: tuple[Any, Table] | None = None

    def query(filters: F) -> tuple[list[R], int]:
        nonlocal queried
        if queried is None or queried[0] != filters:
            queried = (replace(filters), listing.query(filters))  # type: ignore[type-var]
        return queried[1]

    def table_of(rows: list[R], width: int) -> Table:
        nonlocal fitted
        key = (id(rows), width)
        if fitted is None or fitted[0] != key:
            cells = [listing.cells(row) for row in rows]
            fitted = (key, tables.fit(console, listing.layouts, cells, width))
        return fitted[1]

    # Rows a page fits, by terminal size.
    fits: dict[tuple[int, int], int] = {}

    def forget() -> None:
        """The rows may have changed (shown, edited): query them again."""

        nonlocal queried, fitted
        queried = fitted = None

    def page(
        size: tuple[int, int],
        filters: F,
        rows: list[R],
        total: int,
        cursor: int,
        message: str,
    ) -> tui.Frame:
        inner_width, _ = tui.body_size(*size)
        return frame(
            console,
            size,
            listing,
            filters,
            rows,
            total,
            title,
            cursor if rows else None,
            pick,
            message,
            table_of(rows, inner_width) if rows else None,
        )

    with tui.open_screen() as view:
        console = view.console
        # The highlighted row; -1 means the last one of the page.
        cursor = 0
        # Said in the footer until the next key, e.g. "Copied 42".
        message = ""
        while True:
            size = view.size()
            if fit:
                if size not in fits:
                    fits[size] = rows_that_fit(console, listing, *size)
                per_page = fits[size]
                if per_page != filters.per_page:
                    first = (filters.page - 1) * filters.per_page + max(cursor, 0)
                    filters = replace(  # type: ignore[type-var]
                        filters, per_page=per_page, page=first // per_page + 1
                    )
                    cursor = first % per_page
            rows, total = query(filters)
            pages = count_pages(total, filters.per_page)
            if filters.page > pages:
                filters = at_page(pages)
                rows, total = query(filters)
            if cursor < 0 or cursor >= len(rows):
                cursor = max(0, len(rows) - 1)

            # Keys still waiting: handle them first, draw once they're done.
            if not pending:
                view.draw(page(size, filters, rows, total, cursor, message))
                message = ""

            # Ignore keys that do nothing here, without redrawing.
            while True:
                key = next_key()
                if key == RESIZE:
                    action = "redraw"
                    break
                action = key_actions.get(key)
                if action in ROW_ACTIONS and not rows:
                    continue
                at_bottom = cursor == len(rows) - 1
                if action == "down" and at_bottom and filters.page >= pages:
                    continue
                if action == "up" and cursor == 0 and filters.page <= 1:
                    continue
                if action == "first" and cursor == 0 and filters.page <= 1:
                    continue
                if action == "last" and at_bottom and filters.page >= pages:
                    continue
                if action == "next" and filters.page >= pages:
                    continue
                if action == "previous" and filters.page <= 1:
                    continue
                if action == "clear" and not filters.active:
                    continue
                if action is not None:
                    break

            if action == "redraw":
                continue
            if action == "quit":
                return None
            if action == "pick":
                return rows[cursor]
            if action == "copy":
                message = clipboard.copied(
                    str(rows[cursor].id),  # type: ignore[attr-defined]
                    console,
                    what=listing.noun,
                )
            elif action == "open":
                assert listing.show is not None
                listing.show(rows[cursor], view)
                forget()
            elif action == "edit":
                assert listing.edit is not None
                message = listing.edit(rows[cursor], prompter)
                forget()
            elif action == "help":
                drawn = page(size, filters, rows, total, cursor, message)
                view.draw(tui.overlay(console, drawn, help_panel(shortcuts)))
                next_key()
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
                filters, cursor = at_page(pages), -1
            elif action == "clear":
                filters, cursor = listing.clear(filters), 0
            elif action in toggles:
                filters, cursor = toggles[action](filters), 0
                forget()
            else:
                filters = edit_filter(listing, prompter, filters, action, title)
                cursor = 0
