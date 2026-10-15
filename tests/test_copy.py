"""`y` copies what's selected, on every screen: the row under the cursor."""

from datetime import UTC, date, datetime

import pytest

from tests.fakes import FakePrompter, add
from tests.test_sessions_list import keys
from trak import clipboard
from trak.projects import report
from trak.projects.models import Project
from trak.sessions.listing import ListFilters, browse
from trak.sessions.services import start_session, stop_session


@pytest.fixture
def copied(monkeypatch):
    texts = []
    monkeypatch.setattr(
        clipboard, "copy", lambda text, console=None: texts.append(text) or True
    )
    return texts


def test_a_picking_browser_copies_the_highlighted_row(db, copied, capsys):
    for hour in (9, 10):
        start = datetime(2026, 10, 10, hour, tzinfo=UTC)
        stop_session(db, start_session(db, start=start), end=start)

    picked = browse(
        db, FakePrompter(), ListFilters(), read_key=keys("j", "y", "\r"), pick=True
    )

    assert copied == [str(picked.id)] == ["1"]
    assert "Copied 1" in capsys.readouterr().out


def test_the_report_copies_the_project_id(db, copied, capsys):
    project = add(db, Project(name="website"))

    report.show(
        db,
        project,
        read_key=keys("y", "q"),
        now=lambda: datetime.combine(date(2026, 10, 15), datetime.min.time(), UTC),
    )

    assert copied == [str(project.id)]
    assert "Copied 1" in capsys.readouterr().out


def test_nothing_to_copy_on_an_empty_list(db, copied):
    browse(db, FakePrompter(), ListFilters(), read_key=keys("y", "q"), pick=True)

    assert copied == []
