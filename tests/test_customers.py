from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select
from typer.testing import CliRunner

from tests.fakes import FakePrompter, add, frames
from trak.customers import listing
from trak.customers.listing import CustomerFilters, browse
from trak.customers.models import Customer
from trak.customers.services import create_customer, list_customers, update_customer
from trak.projects.models import Project
from trak.prompts import PromptCancelled
from trak.sessions.models import Category, CustomerTag, Tag
from trak.sessions.services import session_totals, start_session, stop_session
from trak.typer_app import app

runner = CliRunner()

START = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def invoke(db, *args: str):
    db.commit()
    return runner.invoke(app, list(args))


def track(db, hours: float, **fields) -> None:
    session = start_session(db, start=START, **fields)
    stop_session(db, session, end=START + timedelta(hours=hours))


# services


def test_create_and_update_customer(db):
    customer = create_customer(db, name="  ACME ")
    assert customer.name == "ACME"

    update_customer(db, customer, name="ACME Inc")

    db.refresh(customer)
    assert customer.name == "ACME Inc"


@pytest.mark.parametrize(
    ("name", "message"), [(" ", "needs a name"), ("ACME", "already a customer")]
)
def test_create_customer_rejects_invalid_names(db, name, message):
    add(db, Customer(name="ACME"))

    with pytest.raises(ValueError, match=message):
        create_customer(db, name=name)


def test_update_customer_rejects_another_customers_name(db):
    acme = add(db, Customer(name="ACME"))
    add(db, Customer(name="Other"))

    update_customer(db, acme, name="ACME")
    with pytest.raises(ValueError, match="already a customer"):
        update_customer(db, acme, name="Other")


def test_list_customers(db):
    for name in ("beta", "Alpha", "gamma"):
        add(db, Customer(name=name))

    assert [c.name for c in list_customers(db)[0]] == ["Alpha", "beta", "gamma"]
    page, total = list_customers(db, name="A", limit=1, offset=1)
    assert ([c.name for c in page], total) == (["beta"], 3)


def test_session_totals_count_direct_and_project_sessions(db):
    acme = add(db, Customer(name="ACME"))
    website = add(db, Project(name="website", customer_fk=acme.id))
    track(db, 1, customer_fk=acme.id)
    track(db, 2, project_fk=website.id)
    track(db, 4)

    totals = session_totals(db, customer_fk=acme.id)

    assert (totals.sessions, totals.time) == (2, timedelta(hours=3))


# trak customers create


def test_create_with_name(cli_db):
    result = invoke(cli_db, "customers", "create", "ACME")

    assert result.exit_code == 0, result.output
    assert "ACME" in result.output and "created" in result.output
    assert [c.name for c in cli_db.exec(select(Customer))] == ["ACME"]


def test_create_a_duplicate(cli_db):
    add(cli_db, Customer(name="ACME"))

    result = invoke(cli_db, "customers", "create", "ACME")

    assert result.exit_code == 1
    assert "already a customer" in result.output


def test_create_without_name_asks_it(interactive, answers, cli_db):
    answers("ACME", "None", "Done")

    result = invoke(cli_db, "customers", "create")

    assert result.exit_code == 0, result.output
    assert [c.name for c in cli_db.exec(select(Customer))] == ["ACME"]


def test_create_without_name_going_back(interactive, answers, cli_db):
    answers(PromptCancelled())

    result = invoke(cli_db, "customers", "create")

    assert result.exit_code == 1
    assert "No customer was created" in result.output


def test_create_without_name_needs_a_terminal(cli_db):
    result = invoke(cli_db, "customers", "create")

    assert result.exit_code == 1
    assert "needs a terminal" in result.output


# trak customers show / edit


def test_customers_id_shows_the_customer(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    website = add(cli_db, Project(name="website", customer_fk=acme.id))
    add(cli_db, Project(name="old", customer_fk=acme.id, archived=True))
    track(cli_db, 1, customer_fk=acme.id)
    track(cli_db, 2, project_fk=website.id)

    result = invoke(cli_db, "customers", str(acme.id))

    assert result.exit_code == 0, result.output
    assert f"Customer #{acme.id}" in result.output
    assert "old (archived), website" in result.output
    assert "3h 0m" in result.output
    assert f'"trak customers edit {acme.id}"' in result.output


def test_show_unknown_customer(cli_db):
    result = invoke(cli_db, "customers", "3")

    assert result.exit_code == 1
    assert "There's no customer #3" in result.output


def test_edit_by_id(interactive, answers, cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    answers("Name", "ACME Inc", "Save")

    result = invoke(cli_db, "customers", "edit", str(acme.id))

    assert result.exit_code == 0, result.output
    cli_db.refresh(acme)
    assert acme.name == "ACME Inc"


def test_edit_without_changes(interactive, answers, cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    answers("Save")

    result = invoke(cli_db, "customers", "edit", str(acme.id))

    assert result.exit_code == 0, result.output
    assert "Nothing changed" in result.output


def test_edit_picks_from_the_browser(interactive, answers, monkeypatch, cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    acme_id = acme.id
    monkeypatch.setattr(
        listing, "browse", lambda db, *a, **k: db.get(Customer, acme_id)
    )
    answers("Name", "ACME Inc", "Save")

    result = invoke(cli_db, "customers", "edit")

    assert result.exit_code == 0, result.output
    cli_db.refresh(acme)
    assert acme.name == "ACME Inc"


# trak customers list


def test_customers_alone_lists_them(cli_db):
    acme = add(cli_db, Customer(name="ACME"))
    add(cli_db, Project(name="website", customer_fk=acme.id))
    track(cli_db, 2, customer_fk=acme.id)

    result = invoke(cli_db, "customers")

    assert result.exit_code == 0, result.output
    assert "ACME" in result.output and "2h 0m" in result.output
    assert "Page 1 of 1 · 1 customer" in result.output


def test_list_by_name(cli_db):
    add(cli_db, Customer(name="ACME"))
    add(cli_db, Customer(name="Other"))

    result = invoke(cli_db, "customers", "list", "-n", "acm")

    assert result.exit_code == 0, result.output
    assert "ACME" in result.output and "Other" not in result.output


def test_browse_filters_by_name(db, capsys):
    add(db, Customer(name="ACME"))
    add(db, Customer(name="Other"))
    pressed = ["/", "q"]

    browse(db, FakePrompter("oth"), CustomerFilters(), read_key=lambda: pressed.pop(0))

    last = frames(capsys.readouterr().out)[-1]
    assert 'Filters: name: "oth"' in last
    assert "Other" in last and "ACME" not in last


def test_create_without_name_can_create_a_category_and_a_tag(
    interactive, answers, cli_db
):
    answers("ACME", "New category", "Retail", "New tag", "vip", "Done")

    result = invoke(cli_db, "customers", "create")

    assert result.exit_code == 0, result.output
    customer = cli_db.exec(select(Customer)).one()
    assert cli_db.get(Category, customer.category_fk).name == "Retail"
    assert [tag.name for tag in cli_db.exec(select(Tag))] == ["vip"]
    assert cli_db.exec(select(CustomerTag)).one().customer_fk == customer.id
