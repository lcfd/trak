"""
Flag parity: whatever the prompts and forms can set, a flag can set too,
so every command works in one line, without a terminal.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import add
from trak.customers.models import Customer
from trak.dates import today
from trak.goals.models import Goal
from trak.labels.links import tag_names
from trak.projects.models import Project
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import get_active_sessions, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def local(moment: datetime) -> str:
    return f"{moment.astimezone():%Y-%m-%d %H:%M}"


def yesterday_at(hour: int) -> datetime:
    day = datetime.now().astimezone() - timedelta(days=1)
    return day.replace(hour=hour, minute=0, second=0, microsecond=0).astimezone(UTC)


def only_session(db) -> Session:
    db.expire_all()
    [session] = db.exec(select(Session)).all()
    return session


@pytest.fixture
def everything(cli_db):
    """A customer, a project without customer, a category and a tag."""

    add(cli_db, Customer(name="ACME"))
    add(cli_db, Project(name="website"))
    add(cli_db, Category(name="dev"))
    add(cli_db, Tag(name="billable"))
    add(cli_db, Tag(name="urgent"))
    return cli_db


# trak start


def test_start_sets_every_field(everything):
    start = yesterday_at(9)

    result = invoke(
        everything, "start", "website", "-n", "Hero", "-c", "ACME",
        "--category", "dev", "-t", "billable", "-t", "urgent", "-s", local(start),
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    session = only_session(everything)
    assert (session.name, session.project_fk, session.customer_fk) == ("Hero", 1, 1)
    assert session.category_fk == 1
    assert tag_names(everything, session) == ["billable", "urgent"]
    assert session.start == start and session.active


def test_start_with_an_association_flag_doesnt_ask_the_project(
    everything, interactive, answers
):
    answers()  # Any prompt would fail: there are no answers.

    result = invoke(everything, "start", "--tag", "billable")

    assert result.exit_code == 0, result.output
    assert only_session(everything).project_fk is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--category", "nope"], "This category doesn't exist"),
        (["--tag", "nope"], "You don't have any tag yet"),
        (["-s", "tomorrow"], "HH:MM"),
    ],
)
def test_start_rejects_bad_flags(cli_db, args, message):
    add(cli_db, Category(name="dev"))

    result = invoke(cli_db, "start", *args)

    assert result.exit_code == 1
    assert message in result.output
    assert get_active_sessions(cli_db) == []


def test_start_refuses_a_second_customer(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    add(cli_db, Customer(name="Initech"))
    add(cli_db, Project(name="website", customer_fk=acme.id))

    refused = invoke(cli_db, "start", "website", "-c", "Initech")
    same = invoke(cli_db, "start", "website", "-c", "ACME")

    assert refused.exit_code == 1
    assert "has its own customer" in refused.output
    assert same.exit_code == 0, same.output
    # The project's customer applies: it isn't stored twice.
    assert only_session(cli_db).customer_fk is None


def test_guided_start_begins_from_the_flags(everything, interactive, answers):
    # The tags start from the flag: "urgent" toggles on, then Done.
    fake = answers("", "website", "ACME", "dev", "urgent", "Done", "")

    result = invoke(everything, "start", "-g", "-c", "ACME", "-t", "billable")

    assert result.exit_code == 0, result.output
    assert fake.defaults["Customer"] == 1
    assert fake.defaults["Category"] is None
    assert fake.notes["Tags"] == "billable, urgent"
    assert tag_names(everything, only_session(everything)) == ["billable", "urgent"]


# trak stop / status


def test_stop_by_id(cli_db):
    first = start_session(cli_db, name="first")
    start_session(cli_db, name="second")

    result = invoke(cli_db, "stop", "--id", str(first.id))

    assert result.exit_code == 0, result.output
    assert [s.name for s in get_active_sessions(cli_db)] == ["second"]


@pytest.mark.parametrize(
    ("session_id", "message"), [("1", "isn't running"), ("9", "no session #9")]
)
def test_stop_by_id_needs_a_running_session(cli_db, session_id, message):
    session = start_session(cli_db)
    stop_session(cli_db, session)

    result = invoke(cli_db, "stop", "--id", session_id)

    assert result.exit_code == 1
    assert message in result.output


def test_status(cli_db):
    assert "No active sessions" in invoke(cli_db, "status").output

    start_session(cli_db, name="Hero")
    result = invoke(cli_db, "status")

    assert result.exit_code == 0, result.output
    assert "Running (1)" in result.output and "Hero" in result.output


# trak sessions create


def test_create_session_sets_every_field(everything):
    start = yesterday_at(9)

    result = invoke(
        everything, "sessions", "create", "website", "-s", local(start), "-e", "1h",
        "-n", "Docs", "-c", "ACME", "--category", "dev", "--tag", "billable,urgent",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    session = only_session(everything)
    assert (session.name, session.category_fk) == ("Docs", 1)
    assert tag_names(everything, session) == ["billable", "urgent"]
    assert session.end == start + timedelta(hours=1)


def test_create_session_without_start_asks_from_the_flags(
    everything, interactive, answers
):
    start = yesterday_at(9)
    fake = answers("", "website", "ACME", "", "", local(start), "", confirm=True)

    result = invoke(
        everything, "sessions", "create", "website", "-n", "Docs", "-e", "30m"
    )

    assert result.exit_code == 0, result.output
    assert fake.defaults["Project"] == 1
    session = only_session(everything)
    assert session.name == "Docs"
    assert session.end - session.start == timedelta(minutes=30)


# trak sessions edit


def test_edit_session_with_flags_needs_no_terminal(everything):
    session = start_session(everything, name="old", customer_fk=1)
    start = yesterday_at(9)

    result = invoke(
        everything, "sessions", "edit", str(session.id), "-n", "new", "-p", "website",
        "-c", "", "--category", "dev", "-t", "billable",
        "-s", local(start), "-e", local(start + timedelta(hours=3)),
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "saved" in result.output
    session = only_session(everything)
    assert (session.name, session.project_fk, session.customer_fk) == ("new", 1, None)
    assert session.category_fk == 1
    assert tag_names(everything, session) == ["billable"]
    assert (session.start, session.end, session.active) == (
        start,
        start + timedelta(hours=3),
        False,
    )


def test_edit_session_clears_with_empty_flags(everything):
    start_session(everything, project_fk=1, tag_fks=[1, 2])

    result = invoke(everything, "sessions", "edit", "1", "-p", "", "-t", "")

    assert result.exit_code == 0, result.output
    session = only_session(everything)
    assert session.project_fk is None
    assert tag_names(everything, session) == []


def test_edit_session_tags_replace_them(everything):
    start_session(everything, tag_fks=[1])

    replaced = invoke(everything, "sessions", "edit", "1", "-t", "urgent")
    same = invoke(everything, "sessions", "edit", "1", "-t", "urgent")

    assert replaced.exit_code == 0, replaced.output
    assert "saved" in replaced.output
    assert tag_names(everything, only_session(everything)) == ["urgent"]
    assert "Nothing changed" in same.output


def test_edit_session_project_with_customer_drops_its_own(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    add(cli_db, Customer(name="Initech"))
    add(cli_db, Project(name="website", customer_fk=acme.id))
    start_session(cli_db, customer_fk=2)

    result = invoke(cli_db, "sessions", "edit", "1", "-p", "website")

    assert result.exit_code == 0, result.output
    assert only_session(cli_db).customer_fk is None


def test_edit_session_rejects_an_end_before_the_start(cli_db):
    start_session(cli_db, start=yesterday_at(9))

    result = invoke(cli_db, "sessions", "edit", "1", "-e", local(yesterday_at(8)))

    assert result.exit_code == 1
    assert "can't end before it starts" in result.output


def test_edit_session_with_the_same_values_changes_nothing(cli_db):
    start_session(cli_db, name="same")

    result = invoke(cli_db, "sessions", "edit", "1", "-n", "same")

    assert result.exit_code == 0
    assert "Nothing changed" in result.output


def test_edit_without_flags_still_needs_a_terminal(cli_db):
    start_session(cli_db)

    result = invoke(cli_db, "sessions", "edit", "1")

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak projects create / edit


def test_create_project_without_name_asks_from_the_flags(cli_db, interactive, answers):
    add(cli_db, Customer(name="ACME"))
    fake = answers("website", "ACME", "", "", "", "")

    result = invoke(
        cli_db, "projects", "create", "-c", "ACME", "-r", "70", "-d", "Pages"
    )

    assert result.exit_code == 0, result.output
    assert fake.defaults["Customer"] == 1
    project = cli_db.exec(select(Project)).one()
    assert (project.rate, project.description) == (70, "Pages")


def test_edit_project_with_flags(cli_db):
    add(cli_db, Customer(name="ACME"))
    project = add(
        cli_db, Project(name="website", customer_fk=1, start=date(2026, 1, 1))
    )

    result = invoke(
        cli_db, "projects", "edit", str(project.id), "-n", "site", "-c", "",
        "-r", "80", "-d", "New", "-s", "", "-e", "2026-12-31", "--archive",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    cli_db.refresh(project)
    assert (project.name, project.customer_fk, project.rate) == ("site", None, 80)
    assert (project.description, project.start, project.end) == (
        "New",
        None,
        date(2026, 12, 31),
    )
    assert project.archived

    result = invoke(cli_db, "projects", "edit", str(project.id), "--unarchive")
    cli_db.refresh(project)
    assert not project.archived


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-e", "2025-01-01"], "end can't come before its start"),
        (["-s", "soon"], "Use YYYY-MM-DD"),
        (["-n", ""], "needs a name"),
    ],
)
def test_edit_project_rejects_bad_flags(cli_db, args, message):
    add(cli_db, Project(name="website", start=date(2026, 1, 1)))

    result = invoke(cli_db, "projects", "edit", "1", *args)

    assert result.exit_code == 1
    assert message in result.output


# Projects and customers: category and tags


def test_projects_and_customers_take_a_category_and_tags(everything):
    project = invoke(
        everything, "projects", "create", "shop", "--category", "dev",
        "-t", "billable", "-t", "urgent",
    )  # fmt: skip
    customer = invoke(
        everything,
        "customers",
        "create",
        "Initech",
        "--category",
        "dev",
        "-t",
        "urgent",
    )
    edited = invoke(everything, "projects", "edit", "2", "--category", "", "-t", "")
    renamed = invoke(everything, "customers", "edit", "2", "-t", "billable")

    for result in (project, customer, edited, renamed):
        assert result.exit_code == 0, result.output
    everything.expire_all()
    shop, initech = everything.get(Project, 2), everything.get(Customer, 2)
    assert (shop.category_fk, tag_names(everything, shop)) == (None, [])
    assert initech.category_fk == 1
    assert tag_names(everything, initech) == ["billable"]


def test_a_tag_that_doesnt_exist_is_an_error(everything):
    result = invoke(everything, "projects", "create", "shop", "-t", "nope")

    assert result.exit_code == 1
    assert "This tag doesn't exist" in result.output
    assert "trak tags create NAME" in result.output


# trak customers edit


def test_edit_customer_with_flags(cli_db):
    add(cli_db, Customer(name="ACME"))
    add(cli_db, Customer(name="Initech"))

    renamed = invoke(cli_db, "customers", "edit", "1", "--name", "ACME Corp")
    taken = invoke(cli_db, "customers", "edit", "1", "--name", "Initech")

    assert renamed.exit_code == 0, renamed.output
    assert taken.exit_code == 1 and "already a customer" in taken.output
    cli_db.expire_all()
    assert cli_db.get(Customer, 1).name == "ACME Corp"


# trak goals create / edit


def test_edit_goal_with_flags(cli_db):
    add(cli_db, Project(name="website"))
    add(cli_db, Project(name="app"))
    goal = add(
        cli_db,
        Goal(project_fk=1, hours=10, start=today(), deadline=today() + timedelta(9)),
    )

    result = invoke(
        cli_db, "goals", "edit", str(goal.id), "-p", "app", "-n", "Launch",
        "-H", "20", "-f", "2026-01-01", "-b", "2026-02-01",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    cli_db.refresh(goal)
    assert (goal.project_fk, goal.name, goal.hours) == (2, "Launch", 20)
    assert (goal.start, goal.deadline) == (date(2026, 1, 1), date(2026, 2, 1))


def test_edit_goal_rejects_a_deadline_before_the_start(cli_db):
    add(cli_db, Project(name="website"))
    add(cli_db, Goal(project_fk=1, hours=10, start=today(), deadline=today()))

    result = invoke(cli_db, "goals", "edit", "1", "-b", "2000-01-01")

    assert result.exit_code == 1
    assert "can't come before its start" in result.output


def test_create_goal_missing_hours_asks_from_the_flags(cli_db, interactive, answers):
    add(cli_db, Project(name="website"))
    fake = answers("", "12", "", "+5", confirm=True)

    result = invoke(cli_db, "goals", "create", "website", "-n", "Launch", "-b", "+5")

    assert result.exit_code == 0, result.output
    # The project was given: not asked again.
    assert fake.asked[0] == "Name"
    assert fake.values["Deadline"] == str(today() + timedelta(days=5))
    goal = cli_db.exec(select(Goal)).one()
    assert (goal.name, goal.hours) == ("Launch", 12)
