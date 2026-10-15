from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlmodel import Session as DBSession
from sqlmodel import col, func, select

from trak.dates import today
from trak.goals.models import Goal
from trak.sessions.services import local_midnight, session_totals

EDITABLE_FIELDS = {"project_fk", "name", "hours", "start", "deadline"}


def check_goal(hours: int, start: date, deadline: date) -> None:
    """Raise ValueError if a goal can't have these hours and days."""

    if hours <= 0:
        raise ValueError("A goal needs at least 1 hour.")
    if deadline < start:
        raise ValueError("A goal's deadline can't come before its start.")


def create_goal(
    db: DBSession,
    *,
    project_fk: int,
    hours: int,
    deadline: date,
    start: date | None = None,
    name: str = "",
) -> Goal:
    """A new Goal; it starts today unless `start` says otherwise."""

    start = start or today()
    check_goal(hours, start, deadline)
    goal = Goal(
        project_fk=project_fk,
        name=name.strip(),
        hours=hours,
        start=start,
        deadline=deadline,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def update_goal(db: DBSession, goal: Goal, **changes: Any) -> Goal:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't edit {', '.join(sorted(unknown))}.")

    if "name" in changes:
        changes["name"] = changes["name"].strip()
    check_goal(
        changes.get("hours", goal.hours),
        changes.get("start", goal.start),
        changes.get("deadline", goal.deadline),
    )

    for field, value in changes.items():
        setattr(goal, field, value)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def goal_conditions(
    *, project_fk: int | None = None, past: bool = False, on: date | None = None
) -> list[Any]:
    conditions: list[Any] = []
    if project_fk is not None:
        conditions.append(Goal.project_fk == project_fk)
    if not past:
        conditions.append(Goal.deadline >= (on or today()))
    return conditions


def list_goals(
    db: DBSession,
    *,
    limit: int = 20,
    offset: int = 0,
    **filters: Any,
) -> tuple[list[Goal], int]:
    """
    A page of Goals, nearest deadline first, and the total matching the
    filters. Goals whose deadline is before `on` (today) are left out
    unless `past`.
    """

    conditions = goal_conditions(**filters)
    total = db.exec(select(func.count()).select_from(Goal).where(*conditions)).one()
    statement = (
        select(Goal)
        .where(*conditions)
        .order_by(col(Goal.deadline), col(Goal.id))
        .limit(limit)
        .offset(offset)
    )
    return list(db.exec(statement)), total


def upcoming_goals(db: DBSession, on: date | None = None) -> list[Goal]:
    """Every Goal whose deadline is `on` (today) or later, nearest first."""

    statement = (
        select(Goal)
        .where(*goal_conditions(on=on))
        .order_by(col(Goal.deadline), col(Goal.id))
    )
    return list(db.exec(statement))


@dataclass
class Progress:
    budget: timedelta
    tracked: timedelta
    # Days from today to the deadline: 0 on the day, negative once it's past.
    days_left: int

    @property
    def reached(self) -> bool:
        return self.tracked >= self.budget

    @property
    def ratio(self) -> float:
        return self.tracked / self.budget


def goal_progress(db: DBSession, goal: Goal, now: datetime | None = None) -> Progress:
    """
    The time tracked on the Goal's Project by Sessions started from its
    `start` to its `deadline`, both days included (running ones count
    until `now`).
    """

    now = now or datetime.now(UTC)
    totals = session_totals(
        db,
        now=now,
        project_fk=goal.project_fk,
        start_from=local_midnight(goal.start),
        start_until=local_midnight(goal.deadline + timedelta(days=1)),
    )
    return Progress(
        budget=timedelta(hours=goal.hours),
        tracked=totals.time,
        days_left=(goal.deadline - now.astimezone().date()).days,
    )
