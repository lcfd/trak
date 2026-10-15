"""
Panes, lazygit style: bordered boxes side by side, one of them focused, each
a list of rows scrolled to its cursor. The home (`main/home.py`) and the
`show` views (`views.py`) are made of them.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from trak import tui

CTRL_D = "\x04"
CTRL_O = "\x0f"
CTRL_U = "\x15"
CTRL_W = "\x17"
BACKSPACE = ("\x7f", "\x08")
ENTER = ("\r", "\n")
UP = ("k", "\x1b[A")
DOWN = ("j", "\x1b[B")
LEFT = ("h", "\x1b[D", "\x1b[Z")
RIGHT = ("l", "\x1b[C", "\t")

SELECTED = Style(bgcolor="grey23")
FOCUSED_BORDER = "bold green"
BORDER = "bright_black"


@dataclass
class Item:
    """A row of a pane: its lines, and its value (None: a heading)."""

    lines: list[Text]
    value: Any = None


class Pane:
    key: str
    title: str
    # Shown when the pane has no rows.
    empty: str = ""
    # (keys, description) of what this pane adds, for the footer and `?`.
    hints: tuple[tuple[str, str], ...] = ()

    def __init__(self) -> None:
        self.cursor = 0
        self.offset = 0

    def items(self, width: int, now: datetime) -> list[Item]:
        raise NotImplementedError

    def subtitle(self, selectable: int) -> str:
        if not selectable:
            return ""
        return f"{self.cursor + 1} of {selectable}"

    def values(self, now: datetime) -> list[Any]:
        return [item.value for item in self.items(80, now) if item.value is not None]

    def selected(self, now: datetime) -> Any:
        values = self.values(now)
        return values[self.cursor] if values else None

    def move(self, to: int, now: datetime) -> None:
        self.cursor = max(0, min(to, len(self.values(now)) - 1))


def heading(text: str, style: str = "bold") -> Item:
    return Item([Text(text, style=style)])


def day_label(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day:%a %d %b %Y}" if day.year != today.year else f"{day:%a %d %b}"


def visible_lines(
    pane: Pane, items: list[Item], height: int
) -> list[tuple[Text, bool]]:
    """
    The `height` lines of `items` the pane shows, scrolled so the row at the
    cursor is in view (headings above the first row too), and whether each is
    part of that row.
    """

    lines: list[tuple[Text, bool]] = []
    span = (0, 0)
    index = 0
    for item in items:
        is_cursor = item.value is not None and index == pane.cursor
        if is_cursor:
            span = (len(lines), len(lines) + len(item.lines))
        lines += [(text, is_cursor) for text in item.lines]
        if item.value is not None:
            index += 1

    top, bottom = span
    if pane.cursor == 0:
        pane.offset = 0
    elif top < pane.offset:
        pane.offset = top
    elif bottom > pane.offset + height:
        pane.offset = min(top, bottom - height)
    pane.offset = max(0, min(pane.offset, len(lines) - height))
    return lines[pane.offset : pane.offset + height]


def box(
    console: Console,
    title: str,
    body: RenderableType,
    width: int,
    height: int,
    *,
    focused: bool,
    subtitle: str = "",
) -> tui.Frame:
    """A bordered box of exactly `width` x `height`, green when focused."""

    panel = Panel(
        body,
        title=f"[bold]{escape(title)}[/bold]" if focused else escape(title),
        title_align="left",
        subtitle=escape(subtitle) or None,
        subtitle_align="right",
        border_style=FOCUSED_BORDER if focused else BORDER,
        padding=(0, 1),
        height=height,
        width=width,
    )
    return tui.render(console, panel, width, height)


def fit_lines(lines: list[Text], width: int) -> Group:
    """Each line cut (or padded) to `width` cells: rows never wrap."""

    for line in lines:
        line.no_wrap = True
        line.truncate(width, overflow="ellipsis", pad=True)
    return Group(*lines)


def render(
    console: Console,
    pane: Pane,
    width: int,
    height: int,
    now: datetime,
    *,
    focused: bool,
    title: str | None = None,
) -> tui.Frame:
    """`pane` in a box: its rows scrolled to the cursor, highlighted if focused."""

    inner = max(1, width - 4)
    items = pane.items(inner, now)
    selectable = sum(1 for item in items if item.value is not None)
    if selectable:
        body: RenderableType = fit_lines(
            [
                Text.assemble(text, style=SELECTED if is_cursor and focused else "")
                for text, is_cursor in visible_lines(pane, items, height - 2)
            ],
            inner,
        )
    else:
        body = Text.from_markup(pane.empty)
    return box(
        console,
        title or f"[{pane.key}] {pane.title}",
        body,
        width,
        height,
        focused=focused,
        subtitle=pane.subtitle(selectable),
    )


def side_by_side(columns: list[tui.Frame]) -> tui.Frame:
    """Frames of the same height joined left to right."""

    return [[s for part in parts for s in part] for parts in zip(*columns)]


def tabs(titles: list[tuple[str, str]], focus: int) -> Text:
    """The panes as tabs, for terminals too narrow to show them side by side."""

    text = Text()
    for index, (key, title) in enumerate(titles):
        style = "bold reverse green" if index == focus else "dim"
        text.append(f" {key} {title} ", style=style)
        text.append("  ")
    return text
