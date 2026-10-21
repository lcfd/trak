from datetime import date
from typing import Any

from sqlmodel import Session as DBSession
from sqlmodel import col, delete, func, select, update

from trak.goals.models import Goal
from trak.labels.links import set_tags
from trak.projects.models import Project
from trak.sessions.models import Session, SessionTag

EDITABLE_FIELDS = {
    "name",
    "customer_fk",
    "description",
    "rate",
    "archived",
    "start",
    "end",
    "category_fk",
    "tag_fks",
}


def get_projects(
    db: DBSession, *, name: str | None = None, archived: bool = False
) -> list[Project]:
    """Projects ordered by name, optionally filtered by exact name."""

    statement = select(Project).order_by(func.lower(Project.name), Project.id)
    if name is not None:
        statement = statement.where(Project.name == name)
    if not archived:
        statement = statement.where(Project.archived == False)
    return list(db.exec(statement))


def check_dates(start: date | None, end: date | None) -> None:
    """Raise ValueError if a project can't run from `start` to `end`."""

    if start is not None and end is not None and end < start:
        raise ValueError("A project's end can't come before its start.")


def check_project(
    db: DBSession,
    name: str,
    rate: int,
    project_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
) -> None:
    """Raise ValueError if a project can't have this name, rate and days."""

    if not name:
        raise ValueError("A project needs a name.")
    if rate < 0:
        raise ValueError("The rate can't be negative.")
    check_dates(start, end)
    if any(p.id != project_id for p in get_projects(db, name=name, archived=True)):
        raise ValueError(f'There\'s already a project called "{name}".')


def create_project(
    db: DBSession,
    *,
    name: str,
    customer_fk: int | None = None,
    description: str = "",
    rate: int = 0,
    start: date | None = None,
    end: date | None = None,
    category_fk: int | None = None,
    tag_fks: list[int] | None = None,
) -> Project:
    name = name.strip()
    check_project(db, name, rate, start=start, end=end)
    project = Project(
        name=name,
        customer_fk=customer_fk,
        description=description.strip(),
        rate=rate,
        start=start,
        end=end,
        category_fk=category_fk,
    )
    db.add(project)
    db.flush()
    set_tags(db, project, tag_fks or [])
    db.commit()
    db.refresh(project)
    return project


def update_project(db: DBSession, project: Project, **changes: Any) -> Project:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't edit {', '.join(sorted(unknown))}.")

    for field in ("name", "description"):
        if field in changes:
            changes[field] = changes[field].strip()
    check_project(
        db,
        changes.get("name", project.name),
        changes.get("rate", project.rate),
        project_id=project.id,
        start=changes.get("start", project.start),
        end=changes.get("end", project.end),
    )

    if "tag_fks" in changes:
        set_tags(db, project, changes.pop("tag_fks"))
    for field, value in changes.items():
        setattr(project, field, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(
    db: DBSession,
    *,
    name: str | None = None,
    customer_fk: int | None = None,
    archived: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Project], int]:
    """
    A page of Projects ordered by name, and the total matching the filters.

    `name` matches case-insensitively anywhere in the name. Archived Projects
    are left out unless `archived`.
    """

    conditions: list[Any] = []
    if name:
        conditions.append(col(Project.name).icontains(name))
    if customer_fk is not None:
        conditions.append(Project.customer_fk == customer_fk)
    if not archived:
        conditions.append(Project.archived == False)

    total = db.exec(select(func.count()).select_from(Project).where(*conditions)).one()
    statement = (
        select(Project)
        .where(*conditions)
        .order_by(func.lower(Project.name), Project.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.exec(statement)), total


def count_project_rows(db: DBSession, project: Project) -> tuple[int, int]:
    """How many Goals and Sessions the Project has."""

    goals = db.exec(
        select(func.count()).select_from(Goal).where(Goal.project_fk == project.id)
    ).one()
    sessions = db.exec(
        select(func.count())
        .select_from(Session)
        .where(Session.project_fk == project.id)
    ).one()
    return goals, sessions


def delete_project(db: DBSession, project: Project, *, sessions: bool = False) -> None:
    """
    Delete it and its Goals (they need a Project). Its Sessions go too with
    `sessions`; otherwise they stay without a project, on its Customer.
    """

    db.exec(delete(Goal).where(Goal.project_fk == project.id))  # type: ignore[call-overload]
    on_project = Session.project_fk == project.id
    if sessions:
        ids = select(Session.id).where(on_project)
        db.exec(delete(SessionTag).where(col(SessionTag.session_fk).in_(ids)))  # type: ignore[call-overload]
        db.exec(delete(Session).where(on_project))  # type: ignore[call-overload]
    else:
        db.exec(
            update(Session)  # type: ignore[call-overload]
            .where(on_project)
            .values(project_fk=None, customer_fk=project.customer_fk)
        )
    set_tags(db, project, [])
    db.delete(project)
    db.commit()
