"""`--json` on every command: one JSON document on stdout, errors on stderr."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
import typer
from typer.core import TyperGroup
from typer.testing import CliRunner

from tests.fakes import add
from trak import output
from trak.customers.models import Customer
from trak.goals.models import Goal
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def invoke_json(db, *args: str):
    """Run `trak ARGS --json`; the result, and stdout parsed."""

    db.commit()
    result = runner.invoke(app, [*args, "--json"])
    data = json.loads(result.stdout) if result.stdout else None
    return result, data


def error_of(result) -> dict:
    assert result.exit_code == 1
    assert result.stdout == ""
    return json.loads(result.stderr)["error"]


def seed(db) -> Project:
    acme = add(db, Customer(name="ACME"))
    website = add(
        db, Project(name="website", customer_fk=acme.id, rate=60, end=date(2099, 1, 1))
    )
    session = start_session(db, start=START, project_fk=website.id)
    stop_session(db, session, end=START + timedelta(hours=2))
    return website


def all_commands(group: TyperGroup, ctx, prefix=""):
    yield prefix.strip(), group
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if isinstance(command, TyperGroup):
            yield from all_commands(command, ctx, f"{prefix} {name}")
        else:
            yield f"{prefix} {name}".strip(), command


# The option


def test_every_command_has_the_json_option():
    root = typer.main.get_command(app)
    ctx = typer.Context(root)

    missing = [
        path
        for path, command in all_commands(root, ctx)
        if not any(p.name == "json" for p in command.params)
    ]

    assert missing == []


def test_json_mode_never_prompts(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert commands.is_interactive()

    output.set_json_mode(True)

    assert not commands.is_interactive()


def test_encode():
    assert output.dumps({"day": date(2026, 10, 1), "time": timedelta(minutes=90)}) == (
        '{"day": "2026-10-01", "time": 5400}'
    )
    moment = json.loads(output.dumps(START))
    assert datetime.fromisoformat(moment) == START


def test_nothing_but_json_even_on_a_new_database(cli_db):
    # No "Created the database" notice, nor the dev bar: stdout is the JSON.
    cli_db.get_bind().dispose()
    from trak import config

    config.DB_PATH.unlink()

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == []


def test_json_works_before_the_command_too(cli_db):
    seed(cli_db)
    cli_db.commit()

    result = runner.invoke(app, ["--json", "projects", "list"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["total"] == 1


def test_bare_trak_is_an_overview(cli_db):
    seed(cli_db)
    add(
        cli_db,
        Goal(project_fk=1, hours=10, start=date.today(), deadline=date(2099, 1, 1)),
    )
    start_session(cli_db, name="now")

    result, data = invoke_json(cli_db)

    assert result.exit_code == 0, result.output
    assert [s["name"] for s in data["active_sessions"]] == ["now"]
    assert [g["project"] for g in data["goals"]] == ["website"]
    assert "version" in data


# Errors


def test_errors_are_json_on_stderr(cli_db):
    result, _ = invoke_json(cli_db, "projects", "show", "7")

    error = error_of(result)
    assert error["title"] == "This project doesn't exist"
    assert "There's no project #7" in error["message"]


def test_what_needs_a_terminal_is_an_error(cli_db):
    seed(cli_db)

    for args in (
        ["sessions", "edit", "1"],
        ["projects", "show"],
        ["customers", "create"],
    ):
        result, _ = invoke_json(cli_db, *args)
        assert "needs a terminal" in error_of(result)["title"]


def test_markup_is_left_out_of_errors(cli_db):
    add(cli_db, Project(name="a"))
    add(cli_db, Project(name="a"))

    result, _ = invoke_json(cli_db, "start", "a")

    assert error_of(result)["message"] == "There are 2 projects called a."


# Sessions


def test_start_and_status_and_stop(cli_db):
    website = seed(cli_db)
    add(cli_db, Category(name="dev"))

    result, started = invoke_json(cli_db, "start", "website", "--category", "dev")
    assert result.exit_code == 0, result.output
    assert started["active"] and started["end"] is None
    assert (started["project"], started["customer"], started["category"]) == (
        "website",
        "ACME",
        "dev",
    )
    assert started["customer_from_project"] and started["customer_fk"] is None
    assert started["project_fk"] == website.id

    _, running = invoke_json(cli_db, "status")
    assert [s["id"] for s in running] == [started["id"]]

    _, stopped = invoke_json(cli_db, "stop")
    assert [s["id"] for s in stopped] == [started["id"]]
    assert not stopped[0]["active"] and stopped[0]["end"]

    _, nothing = invoke_json(cli_db, "stop")
    assert nothing == []


def test_stop_with_several_running_is_an_error(cli_db):
    start_session(cli_db)
    start_session(cli_db)

    result, _ = invoke_json(cli_db, "stop")

    assert "trak stop --id" in error_of(result)["message"]


def test_session_show_create_edit_list(cli_db):
    seed(cli_db)

    _, shown = invoke_json(cli_db, "sessions", "1")
    assert shown["duration_seconds"] == 7200
    assert shown["start"].startswith("2026-10-14T")

    result, created = invoke_json(
        cli_db, "sessions", "create", "-s", "2026-10-13 09:00", "-e", "45m"
    )
    assert result.exit_code == 0, result.output
    assert (created["id"], created["duration_seconds"]) == (2, 45 * 60)

    _, edited = invoke_json(cli_db, "sessions", "edit", "2", "--name", "Docs")
    assert edited["name"] == "Docs"

    _, page = invoke_json(cli_db, "sessions", "list", "--per-page", "1")
    assert (page["total"], page["pages"], page["per_page"]) == (2, 2, 1)
    assert [s["id"] for s in page["items"]] == [1]


def test_list_page_past_the_last(cli_db):
    result, _ = invoke_json(cli_db, "sessions", "list")
    assert result.exit_code == 0
    seed(cli_db)

    result, _ = invoke_json(cli_db, "sessions", "list", "--page", "3")

    assert "doesn't exist" in error_of(result)["title"]


def test_entity_group_alone_lists_in_json(cli_db):
    seed(cli_db)

    _, data = invoke_json(cli_db, "customers")

    assert [c["name"] for c in data["items"]] == ["ACME"]
    assert data["items"][0]["projects"] == [
        {"id": 1, "name": "website", "archived": False}
    ]
    assert data["items"][0]["tracked_seconds"] == 7200


# Projects, customers, goals


def test_project_show_create_edit(cli_db):
    seed(cli_db)

    _, shown = invoke_json(cli_db, "projects", "1")
    assert (shown["customer"], shown["sessions"], shown["tracked_seconds"]) == (
        "ACME",
        1,
        7200,
    )
    assert shown["end"] == "2099-01-01"

    _, created = invoke_json(cli_db, "projects", "create", "app", "-s", "2026-10-01")
    assert (created["name"], created["start"], created["end"]) == (
        "app",
        "2026-10-01",
        None,
    )

    _, edited = invoke_json(cli_db, "projects", "edit", "2", "--archive")
    assert edited["archived"]


def test_project_report(cli_db, monkeypatch):
    seed(cli_db)

    _, report = invoke_json(cli_db, "projects", "report", "1", "--range", "all")

    assert report["range"]["key"] == "all"
    assert report["range"]["end"] == "2099-01-01"
    assert report["tracked_seconds"] == 7200
    assert report["earned"] == 120
    assert {"date": "2026-10-14", "tracked_seconds": 7200} in report["days"]
    days = [d["date"] for d in report["days"]]
    assert days == sorted(days) and len(days) == len(set(days))


def test_project_report_from_to(cli_db):
    seed(cli_db)

    _, report = invoke_json(
        cli_db, "projects", "report", "1", "--from", "2026-10-12", "--to", "2026-10-18"
    )

    assert report["range"] == {
        "key": "custom",
        "label": "Custom",
        "start": "2026-10-12",
        "end": "2026-10-18",
    }
    assert len(report["days"]) == 7
    assert report["tracked_seconds"] == 7200


def test_project_report_bad_days(cli_db):
    seed(cli_db)

    result, _ = invoke_json(
        cli_db, "projects", "report", "1", "--from", "2026-10-12", "--to", "2026-10-01"
    )
    assert "comes before --from" in error_of(result)["message"]

    result, _ = invoke_json(
        cli_db, "projects", "report", "1", "--range", "7d", "--to", "2026-10-01"
    )
    assert "not both" in error_of(result)["message"]


def test_customer_and_goal_create_show_edit(cli_db):
    seed(cli_db)

    _, customer = invoke_json(cli_db, "customers", "create", "Initech")
    assert customer == {
        "id": 2,
        "name": "Initech",
        "category_fk": None,
        "category": None,
        "tag_fks": [],
        "tags": [],
        "projects": [],
        "sessions": 0,
        "tracked_seconds": 0,
        "last_session": None,
    }
    _, renamed = invoke_json(cli_db, "customers", "edit", "2", "--name", "Initrode")
    assert renamed["name"] == "Initrode"

    _, goal = invoke_json(cli_db, "goals", "create", "website", "-H", "10")
    assert (goal["project"], goal["deadline"], goal["reached"]) == (
        "website",
        "2099-01-01",
        False,
    )
    _, edited = invoke_json(cli_db, "goals", "edit", "1", "--hours", "1")
    assert edited["hours"] == 1
    _, shown = invoke_json(cli_db, "goals", "1")
    assert shown["to_go_seconds"] == 3600


def test_doctor(cli_db):
    result, data = invoke_json(cli_db, "doctor")

    assert result.exit_code == 0
    assert data["problems"] == []
    assert data["schema_version"] == data["latest_version"]


def test_dev_fill(cli_db):
    result, data = invoke_json(cli_db, "dev", "fill", "--years", "1")

    assert result.exit_code == 0, result.output
    assert data["database"].endswith("dev_db.sqlite3")
    assert data["to"] == date.today().isoformat()
    assert data["sessions"] > 0 and data["running"] == 2

    result, _ = invoke_json(cli_db, "dev", "fill", "--years", "1")

    assert error_of(result)["title"] == "The dev database isn't empty"


def test_nothing_changed_still_returns_the_row(cli_db):
    seed(cli_db)

    result, data = invoke_json(cli_db, "customers", "edit", "1", "--name", "ACME")

    assert result.exit_code == 0
    assert data["name"] == "ACME"


@pytest.mark.parametrize("model", [Session, Category, Tag])
def test_fields_keep_the_model_order(model):
    row = model(name="x", start=START) if model is Session else model(name="x")

    assert list(output.fields(row)) == list(model.model_fields)
