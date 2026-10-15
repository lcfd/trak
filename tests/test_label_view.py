"""`trak categories|tags show` in a terminal: the label and its sessions."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from tests.fakes import FakePrompter, FakeScreen, add
from trak import clipboard, views
from trak.labels.view import CategoryView, TagView
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.models import Category, Tag
from trak.sessions.services import start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def labelled(cli_db):
    """Design (category) and billable (tag) on Hero, on website; Other has neither."""

    design = add(cli_db, Category(name="Design"))
    project = add(cli_db, Project(name="website", category_fk=design.id))
    billable = add(cli_db, Tag(name="billable"))
    for name, days, fields in (
        ("Hero", 0, {"category_fk": design.id, "tag_fks": [billable.id]}),
        ("Mockups", 1, {"category_fk": design.id}),
        ("Other", 2, {}),
    ):
        start = START - timedelta(days=days)
        session = start_session(
            cli_db, name=name, start=start, project_fk=project.id, **fields
        )
        stop_session(cli_db, session, end=start + timedelta(hours=1))
    cli_db.commit()
    return cli_db


def test_two_panes_the_category_and_its_sessions(labelled):
    screen = FakeScreen(["q"], 120, 30)
    CategoryView(labelled.get_bind(), 1).loop(screen)

    top = screen.last.splitlines()[1]
    assert "[1] Category" in top and "[2] Sessions (2)" in top
    assert "Design" in screen.last and "website" in screen.last
    assert "Hero" in screen.last and "Mockups" in screen.last
    assert "Other" not in screen.last


def test_a_tag_lists_its_sessions(labelled):
    screen = FakeScreen(["q"], 120, 30)
    TagView(labelled.get_bind(), 1).loop(screen)

    assert "[1] Tag" in screen.last and "[2] Sessions (1)" in screen.last
    assert "Hero" in screen.last and "Mockups" not in screen.last


def test_y_copies_the_label_then_the_session(labelled, monkeypatch):
    copied: list[str] = []
    monkeypatch.setattr(
        clipboard, "copy", lambda text, console=None: copied.append(text) or True
    )
    screen = FakeScreen(["y", "2", "j", "y", "q"], 120, 30)
    CategoryView(labelled.get_bind(), 1).loop(screen)

    # [1]: the category. [2]: the session under the cursor (Mockups, the second).
    assert copied == ["1", "2"]
    assert "y copy category id" in screen.frames[0]


def test_e_renames_it_in_place(labelled, monkeypatch):
    monkeypatch.setattr(
        commands,
        "make_prompter",
        lambda: nullcontext(FakePrompter("Name", "UI", "Save")),
    )
    screen = FakeScreen(["e", "q"], 120, 30)
    TagView(labelled.get_bind(), 1).loop(screen)

    assert "Saved" in screen.last and "UI" in screen.last


@pytest.mark.parametrize(
    ("plural", "view"), [("categories", "Category"), ("tags", "Tag")]
)
def test_show_opens_the_view_in_a_terminal(labelled, monkeypatch, plural, view):
    opened = []
    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    monkeypatch.setattr(views, "run", lambda shown: opened.append(shown))

    result = runner.invoke(app, [plural, "show", "1"])

    assert result.exit_code == 0, result.output
    assert type(opened[0]).__name__ == f"{view}View"
    assert opened[0].row_id == 1


def test_plain_prints_the_panel(labelled, monkeypatch):
    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    monkeypatch.setattr(views, "run", lambda shown: pytest.fail("opened the view"))

    result = runner.invoke(app, ["categories", "show", "1", "--plain"])

    assert result.exit_code == 0, result.output
    assert "Category #1" in result.output and "website" in result.output
