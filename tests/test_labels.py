"""Categories and Tags: `trak categories ...`, `trak tags ...`, and their links."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import add
from trak.customers.models import Customer
from trak.db.engine import get_engine
from trak.db.migrations import MIGRATIONS
from trak.labels.links import set_tags, tag_names
from trak.labels.services import CATEGORY, TAG, create_label, list_labels
from trak.projects.models import Project
from trak.sessions.models import Category, Session, SessionTag, Tag
from trak.sessions.services import list_sessions, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def track(db, hours: float = 1, **fields) -> Session:
    session = start_session(db, start=START, **fields)
    return stop_session(db, session, end=START + timedelta(hours=hours))


# services


@pytest.mark.parametrize("kind", [CATEGORY, TAG])
def test_names_are_required_unique_and_without_commas(db, kind):
    create_label(db, kind, name=" Design ")

    for name, message in (
        ("", "needs a name"),
        ("Design", "already"),
        ("a,b", "comma"),
    ):
        with pytest.raises(ValueError, match=message):
            create_label(db, kind, name=name)
    assert [row.name for row in list_labels(db, kind)[0]] == ["Design"]


def test_tags_of_sessions_projects_and_customers(db):
    a, b = add(db, Tag(name="a")), add(db, Tag(name="b"))
    project = add(db, Project(name="website"))
    customer = add(db, Customer(name="ACME"))
    session = start_session(db, tag_fks=[b.id, a.id, a.id])

    set_tags(db, project, [b.id])
    set_tags(db, customer, [a.id, b.id])
    db.commit()

    assert tag_names(db, session) == ["a", "b"]
    assert tag_names(db, project) == ["b"]
    assert tag_names(db, customer) == ["a", "b"]


def test_list_sessions_by_category_and_tag(db):
    design = add(db, Category(name="Design"))
    a, b = add(db, Tag(name="a")), add(db, Tag(name="b"))
    one = track(db, category_fk=design.id, tag_fks=[a.id, b.id])
    two = track(db, tag_fks=[b.id])
    track(db)

    assert list_sessions(db, category_fk=design.id)[0] == [one]
    assert {s.id for s in list_sessions(db, tag_fk=b.id)[0]} == {one.id, two.id}
    assert list_sessions(db, tag_fk=a.id, category_fk=design.id)[1] == 1


# commands


@pytest.mark.parametrize(
    ("plural", "noun"), [("categories", "Category"), ("tags", "Tag")]
)
def test_create_list_show_edit(cli_db, plural, noun):
    created = invoke(cli_db, plural, "create", "Design")
    listed = invoke(cli_db, plural)
    shown = invoke(cli_db, plural, "1")
    edited = invoke(cli_db, plural, "edit", "1", "--name", "UI")

    for result in (created, listed, shown, edited):
        assert result.exit_code == 0, result.output
    assert f"{noun} #1 Design created" in created.output
    assert "Design" in listed.output and f"1 {noun.lower()}" in listed.output
    assert "Sessions" in shown.output
    assert f"{noun} #1 UI saved" in edited.output


def test_show_counts_what_has_the_label(cli_db):
    design = add(cli_db, Category(name="Design"))
    tag = add(cli_db, Tag(name="billable"))
    add(cli_db, Project(name="website", category_fk=design.id))
    acme = add(cli_db, Customer(name="ACME"))
    set_tags(cli_db, acme, [tag.id])
    track(cli_db, hours=2, category_fk=design.id, tag_fks=[tag.id])

    category = invoke(cli_db, "categories", "1")
    tags = invoke(cli_db, "--json", "tags", "1")

    assert "website" in category.output and "2h 0m" in category.output
    assert json.loads(tags.stdout) == {
        "id": 1,
        "name": "billable",
        "projects": [],
        "customers": ["ACME"],
        "sessions": 1,
        "tracked_seconds": 7200,
        "last_session": START.astimezone().isoformat(timespec="seconds"),
    }


def test_list_says_categories(cli_db):
    result = invoke(cli_db, "categories", "list")

    assert "No categories" in result.output


def test_delete_takes_the_label_off_everything(cli_db):
    design = add(cli_db, Category(name="Design"))
    tag = add(cli_db, Tag(name="billable"))
    project = add(cli_db, Project(name="website", category_fk=design.id))
    set_tags(cli_db, project, [tag.id])
    track(cli_db, category_fk=design.id, tag_fks=[tag.id])

    category = invoke(cli_db, "categories", "delete", "1", "--yes")
    tags = invoke(cli_db, "tags", "delete", "1", "-y")

    assert category.exit_code == 0 and tags.exit_code == 0, tags.output
    assert "Category #1 Design deleted" in category.output
    cli_db.expire_all()
    assert cli_db.exec(select(Category)).all() == []
    assert cli_db.exec(select(SessionTag)).all() == []
    assert cli_db.get(Project, 1).category_fk is None
    assert cli_db.get(Session, 1).category_fk is None


def test_delete_needs_yes_without_a_terminal(cli_db):
    add(cli_db, Tag(name="billable"))

    result = invoke(cli_db, "tags", "delete", "1")

    assert result.exit_code == 1
    assert "--yes" in result.output
    assert cli_db.exec(select(Tag)).all()


def test_delete_asks_in_a_terminal(cli_db, interactive, answers):
    add(cli_db, Tag(name="billable"))

    answers(confirm=False)
    kept = invoke(cli_db, "tags", "delete", "1")
    answers(confirm=True)
    deleted = invoke(cli_db, "tags", "delete", "1")

    assert kept.exit_code == 1 and "No tag was deleted" in kept.output
    assert deleted.exit_code == 0, deleted.output
    assert cli_db.exec(select(Tag)).all() == []


def test_create_without_name_asks_it(cli_db, interactive, answers):
    answers("Admin")

    result = invoke(cli_db, "categories", "create")

    assert result.exit_code == 0, result.output
    assert cli_db.exec(select(Category.name)).all() == ["Admin"]


def test_sessions_list_filters_by_category_and_tag(cli_db):
    design = add(cli_db, Category(name="Design"))
    tag = add(cli_db, Tag(name="billable"))
    track(cli_db, name="Mockups", category_fk=design.id, tag_fks=[tag.id])
    track(cli_db, name="Emails")

    by_category = invoke(cli_db, "sessions", "list", "--category", "Design")
    by_tag = invoke(cli_db, "--json", "sessions", "list", "-t", "billable")
    unknown = invoke(cli_db, "sessions", "list", "--tag", "nope")

    assert "Mockups" in by_category.output and "Emails" not in by_category.output
    assert [s["name"] for s in json.loads(by_tag.stdout)["items"]] == ["Mockups"]
    assert unknown.exit_code == 1 and "This tag doesn't exist" in unknown.output


def test_tables_leave_out_empty_label_columns(cli_db):
    track(cli_db, name="Emails")

    result = invoke(cli_db, "sessions", "list")

    assert "Category" not in result.output and "Tags" not in result.output


# migration


def test_migration_moves_the_session_tag_to_the_link_table(tmp_path):
    engine = get_engine(tmp_path / "old.sqlite3")
    with engine.begin() as conn:
        MIGRATIONS[0](conn)
        conn.exec_driver_sql("PRAGMA user_version = 1")
        conn.exec_driver_sql("INSERT INTO tag (id, name) VALUES (1, 'billable')")
        conn.exec_driver_sql(
            "INSERT INTO session (id, name, tag_fk, start, active)"
            " VALUES (1, 'a', 1, '2026-10-10 09:00:00', 0),"
            " (2, 'b', NULL, '2026-10-10 10:00:00', 1)"
        )

    from trak.db.migrations import migrate

    assert migrate(engine)[0] == 2
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT * FROM session_tag").all() == [(1, 1)]
        names = conn.exec_driver_sql("SELECT name, active FROM session").all()
        assert names == [("a", 0), ("b", 1)]
    engine.dispose()
