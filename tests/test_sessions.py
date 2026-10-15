from datetime import UTC, datetime, timedelta

import pytest

from trak.customers.models import Customer
from trak.projects.models import Project
from trak.sessions.models import Session
from trak.sessions.services import get_active_sessions, start_session, stop_session


def test_start_session_creates_an_active_session(db):
    session = start_session(db)

    assert session.id is not None
    assert session.active is True
    assert session.end is None
    assert get_active_sessions(db) == [session]


def test_stop_session_sets_end_and_deactivates(db):
    start = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    session = start_session(db, start=start)

    stopped = stop_session(db, session, end=start + timedelta(hours=2))

    assert stopped.active is False
    assert stopped.end == start + timedelta(hours=2)
    assert get_active_sessions(db) == []


def test_multiple_sessions_can_be_active(db):
    first = start_session(db, start=datetime(2026, 10, 14, 9, 0, tzinfo=UTC))
    second = start_session(db, start=datetime(2026, 10, 14, 10, 0, tzinfo=UTC))

    assert get_active_sessions(db) == [first, second]


def test_stopping_an_inactive_session_fails(db):
    session = stop_session(db, start_session(db))

    with pytest.raises(ValueError, match="not active"):
        stop_session(db, session)


def test_session_cannot_end_before_start(db):
    session = start_session(db, start=datetime(2026, 10, 14, 9, 0, tzinfo=UTC))

    with pytest.raises(ValueError, match="before it starts"):
        stop_session(db, session, end=datetime(2026, 10, 14, 8, 0, tzinfo=UTC))


def test_session_needs_nothing_but_a_start(db):
    session = Session(start=datetime(2026, 10, 14, 9, 0, tzinfo=UTC))
    db.add(session)
    db.commit()

    assert session.project_fk is None
    assert session.customer_fk is None
    assert session.active is False


def test_session_and_project_can_belong_to_a_customer(db):
    customer = Customer(name="ACME")
    db.add(customer)
    db.commit()
    project = Project(name="Website", customer_fk=customer.id)
    db.add(project)
    db.commit()

    with_project = start_session(db, project_fk=project.id)
    customer_only = start_session(db, customer_fk=customer.id)

    assert with_project.project_fk == project.id
    assert customer_only.customer_fk == customer.id
    assert customer_only.project_fk is None
