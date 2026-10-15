from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add
from trak.customers.models import Customer
from trak.dates import today
from trak.projects import listing
from trak.projects.commands import ask_edits, end_text, parse_rate
from trak.projects.listing import ProjectFilters, browse
from trak.projects.models import Project
from trak.projects.services import create_project, list_projects, update_project
from trak.prompts import PromptCancelled
from trak.sessions.services import session_totals, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def track(db, project: Project, hours: float, days_ago: int = 0) -> None:
    start = START - timedelta(days=days_ago)
    session = start_session(db, start=start, project_fk=project.id)
    stop_session(db, session, end=start + timedelta(hours=hours))


# services


def test_create_project(db):
    acme = add(db, Customer(name="ACME"))

    project = create_project(
        db, name="  website ", customer_fk=acme.id, rate=50, description=" Pages "
    )

    assert (project.name, project.customer_fk, project.rate) == ("website", acme.id, 50)
    assert project.description == "Pages"
    assert not project.archived


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"name": "  "}, "needs a name"),
        ({"name": "website"}, "already a project"),
        ({"name": "new", "rate": -1}, "can't be negative"),
    ],
)
def test_create_project_rejects_invalid_fields(db, fields, message):
    add(db, Project(name="website", archived=True))

    with pytest.raises(ValueError, match=message):
        create_project(db, **fields)


def test_update_project(db):
    project = add(db, Project(name="website"))

    update_project(db, project, name="site", rate=60, archived=True)

    db.refresh(project)
    assert (project.name, project.rate, project.archived) == ("site", 60, True)


def test_create_project_with_dates(db):
    project = create_project(
        db, name="website", start=date(2026, 10, 1), end=date(2026, 12, 31)
    )

    assert (project.start, project.end) == (date(2026, 10, 1), date(2026, 12, 31))


def test_create_project_rejects_an_end_before_the_start(db):
    with pytest.raises(ValueError, match="end can't come before its start"):
        create_project(
            db, name="website", start=date(2026, 10, 1), end=date(2026, 9, 30)
        )


def test_update_project_dates_respect_each_other(db):
    project = add(db, Project(name="website", start=date(2026, 10, 1)))

    with pytest.raises(ValueError, match="end can't come before its start"):
        update_project(db, project, end=date(2026, 9, 1))
    # Moving both at once is fine, and so is clearing one.
    update_project(db, project, start=date(2026, 8, 1), end=date(2026, 9, 1))
    update_project(db, project, start=None)

    db.refresh(project)
    assert (project.start, project.end) == (None, date(2026, 9, 1))


def test_update_project_keeps_its_own_name_but_not_others(db):
    project = add(db, Project(name="website"))
    add(db, Project(name="app"))

    update_project(db, project, name="website")
    with pytest.raises(ValueError, match="already a project"):
        update_project(db, project, name="app")
    with pytest.raises(ValueError, match="Can't edit id"):
        update_project(db, project, id=9)


def test_list_projects_filters_and_pages(db):
    acme = add(db, Customer(name="ACME"))
    add(db, Project(name="Website", customer_fk=acme.id))
    add(db, Project(name="web app"))
    add(db, Project(name="old web", archived=True))
    add(db, Project(name="emails"))

    def names(**filters):
        return [p.name for p in list_projects(db, **filters)[0]]

    # Case doesn't matter, neither to filter nor to sort.
    assert names(name="WEB") == ["web app", "Website"]
    assert names(name="web", archived=True) == ["old web", "web app", "Website"]
    assert names(customer_fk=acme.id) == ["Website"]
    page, total = list_projects(db, limit=2, offset=2)
    assert ([p.name for p in page], total) == (["Website"], 3)


def test_session_totals_of_a_project(db):
    website = add(db, Project(name="website"))
    track(db, website, 1, days_ago=2)
    track(db, website, 2.5)

    totals = session_totals(db, project_fk=website.id)

    assert (totals.sessions, totals.time, totals.last) == (
        2,
        timedelta(hours=3.5),
        START,
    )


def test_parse_rate():
    assert parse_rate("") == 0
    assert parse_rate(" 45 ") == 45
    with pytest.raises(ValueError, match="whole number"):
        parse_rate("4.5")


# trak projects create


def test_create_with_options(cli_db):
    add(cli_db, Customer(name="ACME"))

    result = invoke(
        cli_db, "projects", "create", "Web site", "-c", "ACME", "-r", "50", "-d", "x"
    )

    assert result.exit_code == 0, result.output
    assert "Web site" in result.output and "created" in result.output
    assert "trak start 'Web site'" in result.output
    [project] = cli_db.exec(select(Project)).all()
    assert (project.name, project.rate, project.description) == ("Web site", 50, "x")


def test_create_with_dates(cli_db):
    result = invoke(
        cli_db, "projects", "create", "website", "-s", "2026-10-01", "--end", "+30"
    )

    assert result.exit_code == 0, result.output
    [project] = cli_db.exec(select(Project)).all()
    assert project.start == date(2026, 10, 1)
    assert project.end == today() + timedelta(days=30)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--start", "soon"], "Use YYYY-MM-DD"),
        (["-s", "2026-10-01", "-e", "2026-09-01"], "can't come before its start"),
    ],
)
def test_create_with_invalid_dates(cli_db, args, message):
    result = invoke(cli_db, "projects", "create", "website", *args)

    assert result.exit_code == 1
    assert message in result.output
    assert not cli_db.exec(select(Project)).all()


def test_create_with_unknown_customer(cli_db):
    result = invoke(cli_db, "projects", "create", "website", "-c", "Nobody")

    assert result.exit_code == 1
    assert "This customer doesn't exist" in result.output
    assert not cli_db.exec(select(Project)).all()


def test_create_a_duplicate(cli_db):
    add(cli_db, Project(name="website"))

    result = invoke(cli_db, "projects", "create", "website")

    assert result.exit_code == 1
    assert "already a project" in result.output


def test_create_without_name_asks_every_field(interactive, answers, cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    answers("website", "ACME", "40", "Pages", "2026-10-01", "2026-12-31")

    result = invoke(cli_db, "projects", "create")

    assert result.exit_code == 0, result.output
    [project] = cli_db.exec(select(Project)).all()
    assert (project.name, project.customer_fk, project.rate) == ("website", acme.id, 40)
    assert project.description == "Pages"
    assert (project.start, project.end) == (date(2026, 10, 1), date(2026, 12, 31))


def test_create_without_name_leaves_the_dates_empty(interactive, answers, cli_db):
    answers("website", "", "", "", "")

    result = invoke(cli_db, "projects", "create")

    assert result.exit_code == 0, result.output
    [project] = cli_db.exec(select(Project)).all()
    assert (project.start, project.end) == (None, None)


def test_create_without_name_not_confirmed(interactive, answers, cli_db):
    answers("website", "", "", "", "", confirm=False)

    result = invoke(cli_db, "projects", "create")

    assert result.exit_code == 1
    assert "No project was created" in result.output
    assert not cli_db.exec(select(Project)).all()


def test_create_without_name_needs_a_terminal(cli_db):
    result = invoke(cli_db, "projects", "create")

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak projects show


def test_projects_id_shows_the_project(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    website = add(
        cli_db,
        Project(name="website", customer_fk=acme.id, rate=50, description="Pages"),
    )
    track(cli_db, website, 2)

    result = invoke(cli_db, "projects", str(website.id))

    assert result.exit_code == 0, result.output
    assert f"Project #{website.id}" in result.output
    for text in ("website", "ACME", "50/h", "Pages", "active", "2h 0m"):
        assert text in result.output
    assert f'"trak projects edit {website.id}"' in result.output


def test_show_the_dates(cli_db):
    project = add(
        cli_db,
        Project(
            name="website", start=date(2026, 10, 1), end=today() + timedelta(days=3)
        ),
    )

    result = invoke(cli_db, "projects", str(project.id))

    assert result.exit_code == 0, result.output
    assert "Thu 01 Oct 2026" in result.output
    assert "3 days left" in result.output


def test_show_without_dates(cli_db):
    project = add(cli_db, Project(name="website"))

    result = invoke(cli_db, "projects", str(project.id))

    assert result.exit_code == 0, result.output
    assert "Start" in result.output and "End" in result.output


def test_end_text():
    on = date(2026, 10, 14)

    def text(end):
        return end_text(Project(name="p", end=end), on)

    assert text(None) is None
    assert "1 day left" in text(date(2026, 10, 15))
    assert "ends today" in text(on)
    assert "ended 2 days ago" in text(date(2026, 10, 12))


def test_show_unknown_project(cli_db):
    result = invoke(cli_db, "projects", "7")

    assert result.exit_code == 1
    assert "There's no project #7" in result.output


def test_show_picks_among_archived_too(interactive, answers, monkeypatch, cli_db):
    old = add(cli_db, Project(name="old", archived=True))
    old_id = old.id
    seen = {}

    def fake_browse(db, prompter, filters, pick=False, title=""):
        seen["filters"], seen["pick"] = filters, pick
        return db.get(Project, old_id)

    monkeypatch.setattr(listing, "browse", fake_browse)
    answers()

    result = invoke(cli_db, "projects", "show")

    assert result.exit_code == 0, result.output
    assert seen["pick"] and seen["filters"].archived
    assert "archived" in result.output


# trak projects edit


def test_ask_edits(db):
    acme = add(db, Customer(name="ACME"))
    project = add(db, Project(name="website", rate=10))

    prompter = FakePrompter(
        "Name", "site",
        "Customer", "ACME",
        "Rate", "10",  # same value: not a change
        "Archived", "Yes",
        "Save",
    )  # fmt: skip

    changes = ask_edits(db, prompter, project)

    assert changes == {"name": "site", "customer_fk": acme.id, "archived": True}


def test_ask_edits_dates(db):
    project = add(db, Project(name="website", end=date(2026, 12, 31)))

    prompter = FakePrompter(
        "Start", "2026-10-01",
        "End", "",  # cleared
        "Save",
    )  # fmt: skip

    changes = ask_edits(db, prompter, project)

    assert changes == {"start": date(2026, 10, 1), "end": None}


def test_ask_edits_start_checks_the_end(db):
    project = add(db, Project(name="website", end=date(2026, 9, 30)))
    seen = {}

    class Prompter(FakePrompter):
        def input(self, title, **kwargs):
            seen["validator"] = kwargs["validator"]
            return super().input(title, **kwargs)

    ask_edits(db, Prompter("Start", "", "Save"), project)

    with pytest.raises(ValueError, match="can't come before its start"):
        seen["validator"].validate_python("2026-10-01")
    assert seen["validator"].validate_python("2026-09-01") == "2026-09-01"
    assert seen["validator"].validate_python("") == ""


def test_edit_by_id(interactive, answers, cli_db):
    project = add(cli_db, Project(name="website"))
    answers("Rate", "70", "Description", "New pages", "Save")

    result = invoke(cli_db, "projects", "edit", str(project.id))

    assert result.exit_code == 0, result.output
    assert "saved" in result.output
    cli_db.refresh(project)
    assert (project.rate, project.description) == (70, "New pages")


def test_edit_discarding_saves_nothing(interactive, answers, cli_db):
    project = add(cli_db, Project(name="website"))
    answers("Name", "site", PromptCancelled())

    result = invoke(cli_db, "projects", "edit", str(project.id))

    assert result.exit_code == 1
    assert "No changes were saved" in result.output
    cli_db.refresh(project)
    assert project.name == "website"


def test_edit_unknown_project(interactive, cli_db):
    result = invoke(cli_db, "projects", "edit", "5")

    assert result.exit_code == 1
    assert "There's no project #5" in result.output


def test_edit_needs_a_terminal(cli_db):
    project = add(cli_db, Project(name="website"))

    result = invoke(cli_db, "projects", "edit", str(project.id))

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak projects list


def test_projects_alone_lists_them(cli_db):
    website = add(cli_db, Project(name="website", rate=50))
    add(cli_db, Project(name="old", archived=True))
    track(cli_db, website, 1.5)

    result = invoke(cli_db, "projects")

    assert result.exit_code == 0, result.output
    assert "website" in result.output and "50/h" in result.output
    assert "1h 30m" in result.output
    assert "old" not in result.output
    assert "Page 1 of 1 · 1 project" in result.output


def test_list_shows_the_dates(cli_db):
    add(cli_db, Project(name="both", start=date(2026, 10, 1), end=date(2026, 12, 31)))
    add(cli_db, Project(name="open", start=date(2026, 10, 1)))
    add(cli_db, Project(name="due", end=date(2026, 12, 31)))

    result = invoke(cli_db, "projects", "list", "--plain")

    assert result.exit_code == 0, result.output
    assert "2026-10-01 → 2026-12-31" in result.output
    assert "from 2026-10-01" in result.output
    assert "until 2026-12-31" in result.output


def test_list_with_archived_and_customer(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    add(cli_db, Project(name="old", customer_fk=acme.id, archived=True))
    add(cli_db, Project(name="other"))

    result = invoke(cli_db, "projects", "list", "-a", "-c", "ACME")

    assert result.exit_code == 0, result.output
    assert "old" in result.output and "archived" in result.output
    assert "other" not in result.output


def test_list_without_projects(cli_db):
    result = invoke(cli_db, "projects", "list")

    assert result.exit_code == 0
    assert "No project matches these filters" in result.output


def keys(*pressed: str):
    remaining = list(pressed)
    return lambda: remaining.pop(0)


def test_browse_toggles_archived_and_filters_by_name(db, capsys):
    add(db, Project(name="website"))
    add(db, Project(name="old web", archived=True))
    add(db, Project(name="emails"))

    browse(db, FakePrompter("web"), ProjectFilters(), read_key=keys("a", "/", "q"))

    screens = capsys.readouterr().out.split("Projects\n")
    assert "old web" not in screens[1]
    assert "Filters: with archived" in screens[2] and "old web" in screens[2]
    last = screens[-1]
    assert 'name: "web" · with archived' in last
    assert "emails" not in last and "website" in last


def test_browse_picks_a_project(db):
    add(db, Project(name="b"))
    a = add(db, Project(name="a"))

    picked = browse(
        db, FakePrompter(), ProjectFilters(), read_key=keys("\r"), pick=True
    )

    assert picked.id == a.id
