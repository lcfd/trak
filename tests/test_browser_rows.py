"""
Every list browser has a highlighted row: Enter shows it, `e` edits it, `y`
copies its id. Holding a key down never lags behind.
"""

from datetime import UTC, datetime, timedelta

import pytest

from tests.fakes import FakePrompter, FakeScreen, frames
from tests.test_sessions_list import keys
from trak import entities
from trak.customers.models import Customer
from trak.sessions import listing
from trak.sessions.listing import ListFilters, browse
from trak.sessions.models import Session
from trak.sessions.services import start_session, stop_session

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def sessions(db):
    """Five sessions, "s0" the newest (first in the list)."""

    for index in range(5):
        start = START - timedelta(hours=index)
        session = start_session(db, name=f"s{index}", start=start)
        stop_session(db, session, end=start + timedelta(minutes=30))
    return db


def test_the_first_row_is_highlighted_and_j_moves(sessions, monkeypatch):
    shown = []
    monkeypatch.setattr(
        listing, "show_session", lambda db, session, screen: shown.append(session.name)
    )

    browse(sessions, FakePrompter(), ListFilters(), read_key=keys("j", "\r", "q"))

    assert shown == ["s1"]


def test_g_and_shift_g_go_to_the_first_and_last_row(sessions, monkeypatch):
    shown = []
    monkeypatch.setattr(
        listing, "show_session", lambda db, session, screen: shown.append(session.name)
    )

    browse(
        sessions,
        FakePrompter(),
        ListFilters(),
        read_key=keys("G", "\r", "g", "\r", "q"),
    )

    assert shown == ["s4", "s0"]


def test_e_edits_the_row_in_place(sessions, capsys):
    prompter = FakePrompter("Name", "renamed", "Save")

    browse(sessions, prompter, ListFilters(), read_key=keys("j", "e", "q"))

    sessions.expire_all()
    assert sessions.get(Session, 2).name == "renamed"
    out = capsys.readouterr().out
    assert "Saved" in frames(out)[-1]
    # The page is queried again: the new name shows.
    assert "renamed" in frames(out)[-1]


def test_e_then_esc_saves_nothing(sessions, capsys):
    from trak.prompts import PromptCancelled

    browse(
        sessions,
        FakePrompter(PromptCancelled()),
        ListFilters(),
        read_key=keys("e", "q"),
    )

    assert "No changes were saved" in frames(capsys.readouterr().out)[-1]


def test_keys_typed_together_are_handled_before_drawing(sessions, monkeypatch, capsys):
    shown = []
    monkeypatch.setattr(
        listing, "show_session", lambda db, session, screen: shown.append(session.name)
    )

    # A key held down: the terminal sends the repeats faster than frames draw.
    browse(sessions, FakePrompter(), ListFilters(), read_key=keys("jjj", "\r", "q"))

    assert shown == ["s3"]
    # One frame first, one after the three j, one after showing the row.
    assert len(frames(capsys.readouterr().out)) == 3


def test_moving_the_cursor_queries_the_page_once(sessions, monkeypatch):
    calls = []
    original = listing.query
    monkeypatch.setattr(
        listing, "query", lambda db, filters: calls.append(1) or original(db, filters)
    )
    cells = []
    original_cells = listing.session_cells
    monkeypatch.setattr(
        listing,
        "session_cells",
        lambda db, session: cells.append(1) or original_cells(db, session),
    )

    browse(
        sessions, FakePrompter(), ListFilters(), read_key=keys("j", "j", "k", "j", "q")
    )

    assert len(calls) == 1
    # The cells of the five rows once, however many keys.
    assert len(cells) == 5


def test_show_printed_waits_for_a_key(capsys):
    screen = FakeScreen([None, "x"])

    entities.show_printed(screen, lambda: print("the panel"))

    assert screen.suspensions == 1 and screen.keys == []
    assert "the panel" in capsys.readouterr().out


def test_customers_enter_prints_the_customer(db, monkeypatch, capsys):
    from trak.customers import listing as customers
    from trak.customers.listing import CustomerFilters

    db.add(Customer(name="ACME"))
    db.commit()
    shown = []
    monkeypatch.setattr(
        entities, "show_printed", lambda screen, show: shown.append(show) or show()
    )

    customers.browse(db, FakePrompter(), CustomerFilters(), read_key=keys("\r", "q"))

    assert len(shown) == 1
    assert "Customer #1" in capsys.readouterr().out
