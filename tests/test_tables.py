"""Tables fit their width by changing layout, not by cutting everything."""

from rich.console import Console

from tests.fakes import add
from trak import tables
from trak.sessions import listing
from trak.sessions.models import Category, Tag
from trak.sessions.services import start_session, stop_session
from trak.tables import col, fit, share


def render(table, width: int) -> str:
    console = Console(width=width, color_system=None)
    with console.capture() as capture:
        console.print(table)
    return capture.get()


ROWS = [
    {"id": "1", "name": "Feature work", "start": "2026-10-15 09:00", "end": "10:30",
     "when": "15 Oct 09:00–10:30", "duration": "1h 30m", "note": ""},
    {"id": "22", "name": "Call", "start": "2026-10-15 11:00", "end": "11:30",
     "when": "15 Oct 11:00–11:30", "duration": "0h 30m", "note": ""},
]  # fmt: skip
LAYOUTS = [
    [tables.ID, col("name", flex=True), col("start"), col("end"), col("duration")],
    [tables.ID, col("name", flex=True), col("when"), col("duration")],
    [tables.ID, col("name", flex=True), col("duration")],
]


def headers(table) -> list[str]:
    return [str(column.header) for column in table.columns]


def test_the_widest_layout_that_fits():
    console = Console(width=200)

    assert headers(fit(console, LAYOUTS, ROWS, 80)) == [
        "#", "Name", "Start", "End", "Duration",
    ]  # fmt: skip
    # Start and End grouped into When before anything is cut.
    assert headers(fit(console, LAYOUTS, ROWS, 55)) == ["#", "Name", "When", "Duration"]
    assert headers(fit(console, LAYOUTS, ROWS, 30)) == ["#", "Name", "Duration"]


def test_only_the_flex_column_is_cut():
    console = Console(width=200)

    out = render(fit(console, LAYOUTS, ROWS, 24), 24)

    # 24 cells: the name gives way, the duration stays whole.
    assert "1h 30m" in out and "0h 30m" in out
    assert "Feature…" in out or "Featu…" in out
    assert all(len(line) <= 24 for line in out.splitlines())


def test_dates_are_never_cut_while_a_layout_fits():
    console = Console(width=200)

    for width in range(30, 90):
        out = render(fit(console, LAYOUTS, ROWS, width), width)
        assert "…" not in out, width


def test_optional_columns_leave_when_empty():
    console = Console(width=200)
    layout = [[tables.ID, col("name", flex=True), col("note", optional=True)]]

    assert headers(fit(console, layout, ROWS, 80)) == ["#", "Name"]
    with_note = [{**ROWS[0], "note": "hi"}, ROWS[1]]
    assert headers(fit(console, layout, with_note, 80)) == ["#", "Name", "Note"]


def test_share_gives_narrow_columns_what_they_need():
    assert share([5, 30], 20) == [5, 15]
    assert share([30, 30], 20) == [10, 10]
    assert share([3, 4], 20) == [3, 4]
    assert share([10], 0) == [1]


def test_sessions_list_keeps_whole_values_at_80_columns(db):
    design = add(db, Category(name="Design"))
    tag = add(db, Tag(name="billable"))
    from datetime import UTC, datetime, timedelta

    start = datetime(2026, 10, 10, 9, tzinfo=UTC)
    session = start_session(
        db, name="Mockups", start=start, category_fk=design.id, tag_fks=[tag.id]
    )
    stop_session(db, session, end=start + timedelta(hours=1))
    cells = [listing.session_cells(db, session)]

    for width in (120, 100, 80, 60, 40):
        out = render(fit(Console(width=width), listing.LAYOUTS, cells, width), width)
        assert "1h 0m" in out, width
        assert "Mockups" in out, width
        assert all(len(line) <= width for line in out.splitlines()), width
