"""
Deleting every entity: the services, `trak <entities> delete`, and `D` in the
home, the list browsers and the `show` views (asking first).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter, FakeScreen, add
from tests.test_sessions_list import keys
from trak.customers.models import Customer
from trak.customers.services import delete_customer
from trak.goals import listing as goals_listing
from trak.goals.models import Goal
from trak.goals.services import delete_goal
from trak.goals.view import GoalView
from trak.projects.models import Project
from trak.projects.services import delete_project
from trak.sessions import listing as sessions_listing
from trak.sessions.listing import ListFilters
from trak.sessions.models import (
    CustomerTag,
    ProjectTag,
    Session,
    SessionTag,
    Tag,
)
from trak.sessions.services import delete_session, start_session, stop_session
from trak.sessions.view import SessionView
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def make(db, name: str, hours: int = 0, **fields) -> Session:
    start = START - timedelta(hours=hours)
    session = start_session(db, name=name, start=start, **fields)
    return stop_session(db, session, end=start + timedelta(minutes=30))


@pytest.fixture
def world(cli_db):
    """ACME with website (a goal, two sessions), a direct session, and a tag."""

    db = cli_db
    tag = add(db, Tag(name="billable"))
    acme = add(db, Customer(name="ACME"))
    website = add(db, Project(name="website", customer_fk=acme.id))
    add(db, ProjectTag(project_fk=website.id, tag_fk=tag.id))
    add(db, CustomerTag(customer_fk=acme.id, tag_fk=tag.id))
    add(
        db,
        Goal(
            project_fk=website.id,
            hours=10,
            start=date(2026, 10, 1),
            deadline=date(2026, 10, 31),
        ),
    )
    make(db, "Hero", project_fk=website.id, tag_fks=[tag.id])
    make(db, "Docs", hours=1, project_fk=website.id)
    make(db, "Call", hours=2, customer_fk=acme.id)
    db.commit()
    return db


def count(db, model) -> int:
    db.expire_all()
    return len(list(db.exec(select(model))))


# Services


def test_delete_session_takes_its_tags(world):
    hero = world.exec(select(Session).where(Session.name == "Hero")).one()

    delete_session(world, hero)

    assert count(world, Session) == 2
    assert count(world, SessionTag) == 0
    assert count(world, Tag) == 1


def test_delete_goal_keeps_the_sessions(world):
    delete_goal(world, world.exec(select(Goal)).one())

    assert count(world, Goal) == 0
    assert count(world, Session) == 3


def test_delete_project_keeps_its_sessions_on_its_customer(world):
    website = world.exec(select(Project)).one()
    acme_id = website.customer_fk

    delete_project(world, website)

    assert count(world, Project) == count(world, Goal) == count(world, ProjectTag) == 0
    sessions = list(world.exec(select(Session)))
    assert len(sessions) == 3
    assert all(s.project_fk is None and s.customer_fk == acme_id for s in sessions)


def test_delete_project_with_its_sessions(world):
    delete_project(world, world.exec(select(Project)).one(), sessions=True)

    assert [s.name for s in world.exec(select(Session))] == ["Call"]
    assert count(world, SessionTag) == 0


def test_delete_customer_keeps_its_projects_and_sessions(world):
    delete_customer(world, world.exec(select(Customer)).one())

    assert count(world, Customer) == count(world, CustomerTag) == 0
    assert world.exec(select(Project)).one().customer_fk is None
    assert count(world, Session) == 3
    assert all(s.customer_fk is None for s in world.exec(select(Session)))


# Commands


@pytest.mark.parametrize(
    "args, model, left",
    [
        (["sessions", "delete", "1"], Session, 2),
        (["goals", "delete", "1"], Goal, 0),
        (["projects", "delete", "1"], Project, 0),
        (["customers", "delete", "1"], Customer, 0),
        (["tags", "delete", "1"], Tag, 0),
    ],
)
def test_delete_with_yes_needs_no_terminal(world, args, model, left):
    result = runner.invoke(app, [*args, "--yes"])

    assert result.exit_code == 0, result.output
    assert "deleted" in result.output
    assert count(world, model) == left


@pytest.mark.parametrize("entities", ["sessions", "goals", "projects", "customers"])
def test_delete_without_yes_needs_a_terminal(world, entities):
    result = runner.invoke(app, [entities, "delete", "1"])

    assert result.exit_code == 1
    assert "--yes" in result.output


def test_delete_of_a_missing_row_is_an_error(world):
    result = runner.invoke(app, ["sessions", "delete", "99", "--yes"])

    assert result.exit_code == 1
    assert "no session #99" in result.output


def test_delete_asks_first_in_a_terminal(world, interactive, answers):
    answers(confirm=False)

    result = runner.invoke(app, ["projects", "delete", "1"])

    assert result.exit_code == 1
    assert "No project was deleted" in result.output
    assert count(world, Project) == 1


def test_delete_says_what_goes_with_it(world, interactive, monkeypatch):
    asked = []

    class Asking(FakePrompter):
        def confirm(self, label, default=True):
            asked.append(label)
            return True

    from contextlib import nullcontext

    from trak.sessions import commands

    monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(Asking()))

    result = runner.invoke(app, ["projects", "delete", "1"])

    assert result.exit_code == 0, result.output
    assert asked == [
        (
            "Delete the project website? Its 1 goal goes too. "
            "Its 2 sessions stay, on its customer."
        )
    ]


def test_project_delete_with_sessions(world):
    result = runner.invoke(app, ["projects", "delete", "1", "--with-sessions", "-y"])

    assert result.exit_code == 0, result.output
    assert "Its 1 goal and 2 sessions go too." in result.output
    assert count(world, Session) == 1


# Full screen


def test_shift_d_in_the_browser_deletes_the_row_after_asking(world):
    sessions_listing.browse(
        world, FakePrompter(), ListFilters(), read_key=keys("j", "D", "y", "q")
    )

    assert sorted(s.name for s in world.exec(select(Session))) == ["Call", "Hero"]


def test_any_other_key_keeps_the_row(world):
    sessions_listing.browse(
        world, FakePrompter(), ListFilters(), read_key=keys("D", "n", "q")
    )

    assert count(world, Session) == 3


def test_goals_browser_deletes_too(world):
    from trak.goals.listing import GoalFilters

    goals_listing.browse(
        world, FakePrompter(), GoalFilters(past=True), read_key=keys("D", "y", "q")
    )

    assert count(world, Goal) == 0


def test_shift_d_in_a_view_deletes_the_row_and_ends(world):
    screen = FakeScreen(["D", "y"], 120, 30)
    view = GoalView(world.get_bind(), 1)

    view.loop(screen)

    assert "Delete the goal #1 website?" in screen.frames[-1]
    assert count(world, Goal) == 0
    assert "Deleted" in view.deleted


def test_shift_d_on_the_list_pane_deletes_the_session_under_the_cursor(world):
    hero = world.exec(select(Session).where(Session.name == "Hero")).one().id
    # No read left open: the view writes with connections of its own.
    world.commit()
    # [2] lists the project's sessions: Hero, then Docs.
    screen = FakeScreen(["2", "j", "D", "y", "q"], 120, 30)

    SessionView(world.get_bind(), hero).loop(screen)

    assert sorted(s.name for s in world.exec(select(Session))) == ["Call", "Hero"]
    assert "Deleted" in screen.last


def test_deleting_the_session_shown_goes_back_to_the_one_before(world):
    hero = world.exec(select(Session).where(Session.name == "Hero")).one().id
    # No read left open: the view writes with connections of its own.
    world.commit()
    # Show Docs from Hero's list, then delete it: back on Hero.
    screen = FakeScreen(["2", "j", "\r", "1", "D", "y", "q"], 120, 30)
    view = SessionView(world.get_bind(), hero)

    view.loop(screen)

    assert view.row_id == hero and not view.deleted
    assert count(world, Session) == 2


def test_the_home_deletes_the_session_selected(world, monkeypatch):
    from contextlib import contextmanager

    from tests.test_home import trak
    from trak.main import menu
    from trak.sessions import commands

    fake = FakeScreen(["2", "D", "y", "q"], 120, 40)

    @contextmanager
    def screen():
        yield fake

    monkeypatch.setattr(commands, "is_interactive", lambda: True)
    monkeypatch.setattr(menu, "open_screen", screen)

    trak()

    assert count(world, Session) == 2
    assert "Deleted" in fake.last


def test_its_agrees_with_what_it_counts():
    from trak.deleting import its

    verbs = ("goes too.", "go too.")
    assert its([(1, "goal"), (0, "session")], verbs) == "Its 1 goal goes too."
    assert its([(1, "goal"), (2, "session")], verbs) == (
        "Its 1 goal and 2 sessions go too."
    )
    assert its([(0, "goal")], verbs) == ""
