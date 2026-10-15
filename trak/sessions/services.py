from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlmodel import Session as DBSession
from sqlmodel import col, func, or_, select

from trak.projects.models import Project
from trak.sessions.models import Session


def get_active_sessions(db: DBSession) -> list[Session]:
    statement = select(Session).where(Session.active).order_by(Session.start)
    return list(db.exec(statement))


def start_session(
    db: DBSession,
    *,
    name: str = "",
    project_fk: int | None = None,
    customer_fk: int | None = None,
    category_fk: int | None = None,
    tag_fk: int | None = None,
    start: datetime | None = None,
) -> Session:
    session = Session(
        name=name.strip(),
        project_fk=project_fk,
        customer_fk=customer_fk,
        category_fk=category_fk,
        tag_fk=tag_fk,
        start=start or datetime.now(UTC),
        active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_session(
    db: DBSession,
    *,
    start: datetime,
    end: datetime,
    now: datetime | None = None,
    **fields: Any,
) -> Session:
    """A past, stopped Session: for time tracked without `trak start`."""

    if end < start:
        raise ValueError("A session can't end before it starts.")
    if end > (now or datetime.now(UTC)):
        raise ValueError("A session can't end in the future.")

    session = Session(start=start, end=end, active=False, **fields)
    session.name = session.name.strip()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def stop_session(
    db: DBSession, session: Session, end: datetime | None = None
) -> Session:
    if not session.active:
        raise ValueError(f"Session {session.id} is not active.")

    end = end or datetime.now(UTC)
    if end < session.start:
        raise ValueError("A session can't end before it starts.")

    session.end = end
    session.active = False
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


EDITABLE_FIELDS = {
    "name",
    "project_fk",
    "customer_fk",
    "category_fk",
    "tag_fk",
    "start",
    "end",
}


def update_session(db: DBSession, session: Session, **changes: Any) -> Session:
    """
    Change the editable fields of a Session. Giving an active Session an
    `end` stops it.
    """

    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't edit {', '.join(sorted(unknown))}.")

    start = changes.get("start", session.start)
    end = changes.get("end", session.end)
    if end is not None and end < start:
        raise ValueError("A session can't end before it starts.")
    if session.end is not None and "end" in changes and end is None:
        raise ValueError("A stopped session can't be running again.")

    for field, value in changes.items():
        setattr(session, field, value.strip() if field == "name" else value)
    if session.end is not None:
        session.active = False

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def local_midnight(day: date) -> datetime:
    """Midnight at the start of `day` in local time, as UTC."""

    return datetime.combine(day, time()).astimezone().astimezone(UTC)


def session_conditions(
    *,
    project_fk: int | None = None,
    customer_fk: int | None = None,
    name: str | None = None,
    start_from: datetime | None = None,
    start_until: datetime | None = None,
) -> list[Any]:
    """
    The WHERE conditions of a Session query; see `list_sessions`.
    """

    conditions: list[Any] = []
    if project_fk is not None:
        conditions.append(Session.project_fk == project_fk)
    if customer_fk is not None:
        customer_projects = select(Project.id).where(Project.customer_fk == customer_fk)
        conditions.append(
            or_(
                Session.customer_fk == customer_fk,
                col(Session.project_fk).in_(customer_projects),
            )
        )
    if name:
        conditions.append(col(Session.name).icontains(name))
    if start_from is not None:
        conditions.append(Session.start >= start_from)
    if start_until is not None:
        conditions.append(Session.start < start_until)
    return conditions


def list_sessions(
    db: DBSession,
    *,
    limit: int = 20,
    offset: int = 0,
    **filters: Any,
) -> tuple[list[Session], int]:
    """
    A page of Sessions, newest first, and the total matching the filters.

    `customer_fk` matches Sessions of that Customer, directly or through their
    Project. `name` matches case-insensitively anywhere in the name. The start
    range includes `start_from` and excludes `start_until`.
    """

    conditions = session_conditions(**filters)
    total = db.exec(select(func.count()).select_from(Session).where(*conditions)).one()
    statement = (
        select(Session)
        .where(*conditions)
        .order_by(col(Session.start).desc(), col(Session.id).desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.exec(statement)), total


@dataclass
class Totals:
    sessions: int = 0
    time: timedelta = timedelta()
    last: datetime | None = None


def session_totals(
    db: DBSession, now: datetime | None = None, **filters: Any
) -> Totals:
    """
    How many Sessions match the filters (as in `list_sessions`), their total
    time (running ones count until `now`) and the start of the latest one.
    """

    now = now or datetime.now(UTC)
    totals = Totals()
    for session in db.exec(select(Session).where(*session_conditions(**filters))):
        totals.sessions += 1
        totals.time += (session.end or now) - session.start
        if totals.last is None or session.start > totals.last:
            totals.last = session.start
    return totals
