"""
Tables that fit the width they have, without scrollbars or wrapping.

A list declares its columns as a ladder of `Layout`s, from the widest to the
narrowest. The table takes the first layout whose columns all fit at their
natural width; only its `flex` columns (names, labels) may shrink, down to
`least` cells. Going down the ladder, a list:

1. groups related columns into one (Start and End become "When"),
2. switches to shorter formats (dates without the year),
3. leaves out what matters least (it's all in the row's `show`).

Ids, dates, numbers and durations are never cut: only flex columns get an
ellipsis, and the last layout is the only one where even that may not fit.

The cells of a row are worked out once (`cells`, a dict of markup by key)
and every layout reads them, so trying the layouts costs no queries.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from rich.console import Console
from rich.table import Table
from rich.text import Text

Cells = dict[str, str]


@dataclass(frozen=True)
class Column:
    header: str
    # The cell of a row, as markup, from the row's cells.
    cell: Callable[[Cells], str]
    justify: Literal["left", "right"] = "left"
    style: str | None = None
    # A column that gives way when room is short; the only kind ever cut.
    flex: bool = False
    # How narrow a flex column may get in a layout that "fits".
    least: int = 14
    # Left out when it's empty on every row shown.
    optional: bool = False


def col(
    key: str,
    header: str | None = None,
    *,
    right: bool = False,
    style: str | None = None,
    flex: bool = False,
    least: int = 14,
    optional: bool = False,
) -> Column:
    """A column showing the cell `key` as it is."""

    return Column(
        header if header is not None else key.capitalize(),
        lambda cells: cells.get(key, ""),
        justify="right" if right else "left",
        style=style,
        flex=flex,
        least=least,
        optional=optional,
    )


Layout = Sequence[Column]

# Each column has a cell of padding on both sides, and a line between two.
GAP = 3


def _width(console: Console, markup: str) -> int:
    return console.measure(Text.from_markup(markup)).maximum if markup else 0


def _columns(layout: Layout, rows: list[Cells]) -> list[Column]:
    """The columns shown: optional ones only when a row has something there."""

    return [
        column
        for column in layout
        if not column.optional or any(column.cell(row).strip() for row in rows)
    ]


def fit(
    console: Console,
    layouts: Sequence[Layout],
    rows: list[Cells],
    width: int,
    cursor: int | None = None,
) -> Table:
    """
    The table of `rows` in the first layout that fits `width` (or the last
    one, its flex columns cut to make it fit), the row at `cursor` highlighted.
    """

    for index, layout in enumerate(layouts):
        columns = _columns(layout, rows)
        texts = [[column.cell(row) for row in rows] for column in columns]
        widths = [
            max([_width(console, column.header), *(_width(console, t) for t in cells)])
            for column, cells in zip(columns, texts)
        ]
        room = width - GAP * len(columns) + 1
        flexes = [i for i, c in enumerate(columns) if c.flex]
        fixed = sum(w for i, w in enumerate(widths) if i not in flexes)
        least = sum(min(widths[i], columns[i].least) for i in flexes)
        if fixed + least <= room or index == len(layouts) - 1:
            needs = [widths[i] for i in flexes]
            for i, given in zip(flexes, share(needs, max(0, room - fixed))):
                widths[i] = given
            return _table(columns, texts, widths, set(flexes), cursor)
    raise ValueError("A table needs at least one layout.")


def share(needs: list[int], room: int) -> list[int]:
    """
    `room` cells shared by columns needing `needs`: the narrow ones get what
    they need, the others split what's left (at least 1 cell each).
    """

    given = [0] * len(needs)
    left = list(range(len(needs)))
    while left:
        fair = room // len(left)
        fits = [i for i in left if needs[i] <= fair]
        if not fits:
            for i in left:
                given[i] = max(1, fair)
            break
        for i in fits:
            given[i] = needs[i]
            room -= needs[i]
            left.remove(i)
    return given


def _table(
    columns: list[Column],
    texts: list[list[str]],
    widths: list[int],
    flexes: set[int],
    cursor: int | None,
) -> Table:
    table = Table(header_style="bold", show_edge=False)
    for index, column in enumerate(columns):
        table.add_column(
            column.header,
            justify=column.justify,
            style=column.style,
            no_wrap=True,
            overflow="ellipsis",
            # A flex column gets exactly its share; the others what they need.
            width=widths[index] if index in flexes else None,
        )
    for row in range(len(texts[0]) if texts else 0):
        table.add_row(
            *(cells[row] for cells in texts),
            style="reverse" if row == cursor else None,
        )
    return table


# Shorter formats, for the narrower layouts.


def short_day(day: date, today: date) -> str:
    """ "15 Oct", with the year when it isn't this one: "15 Oct 2025"."""

    return f"{day:%d %b}" if day.year == today.year else f"{day:%d %b %Y}"


ID = col("id", "#", right=True, style="dim")
