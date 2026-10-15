"""
Tags of a Session, a Project or a Customer: any number each, through their
link tables (`session_tag`, `project_tag`, `customer_tag`).

Forms and flags edit them as `tag_fks`, a sorted list of ids, as if it were
a field of the row (`with_tags`).
"""

from typing import Any

from rich.markup import escape
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, col, delete, select

from trak.customers.models import Customer
from trak.projects.models import Project
from trak.sessions.models import (
    Category,
    CustomerTag,
    ProjectTag,
    Session,
    SessionTag,
    Tag,
)

# The model -> its link table and the column naming the row there.
LINKS: dict[type, tuple[Any, str]] = {
    Session: (SessionTag, "session_fk"),
    Project: (ProjectTag, "project_fk"),
    Customer: (CustomerTag, "customer_fk"),
}


def _link(row: SQLModel) -> tuple[Any, Any]:
    link, column = LINKS[type(row)]
    return link, getattr(link, column)


def tags_of(db: DBSession, row: SQLModel) -> list[Tag]:
    """The row's Tags, by name."""

    if getattr(row, "id", None) is None:
        return []
    link, owner = _link(row)
    statement = (
        select(Tag)
        .join(link, link.tag_fk == Tag.id)
        .where(owner == row.id)  # type: ignore[attr-defined]
        .order_by(Tag.name, Tag.id)
    )
    return list(db.exec(statement))


def tag_fks_of(db: DBSession, row: SQLModel) -> list[int]:
    return sorted(tag.id for tag in tags_of(db, row) if tag.id is not None)


def tag_names(db: DBSession, row: SQLModel) -> list[str]:
    return [tag.name for tag in tags_of(db, row)]


def set_tags(db: DBSession, row: SQLModel, tag_fks: list[int]) -> None:
    """Give the row exactly these Tags (it needs an id). Doesn't commit."""

    link, owner = _link(row)
    row_id = row.id  # type: ignore[attr-defined]
    db.exec(delete(link).where(owner == row_id))  # type: ignore[call-overload]
    _, column = LINKS[type(row)]
    db.add_all(link(**{column: row_id, "tag_fk": fk}) for fk in sorted(set(tag_fks)))


def tagged_with(model: type, tag_fk: int) -> Any:
    """A condition: the `model` row has the Tag `tag_fk`."""

    link, column = LINKS[model]
    owners = select(getattr(link, column)).where(link.tag_fk == tag_fk)
    return col(model.id).in_(owners)  # type: ignore[attr-defined]


class WithTags:
    """A row that also answers `tag_fks`, for forms and `effective_changes`."""

    def __init__(self, row: Any, tag_fks: list[int]) -> None:
        self._row = row
        self.tag_fks = tag_fks

    def __getattr__(self, name: str) -> Any:
        return getattr(self._row, name)


def with_tags(db: DBSession, row: Any) -> WithTags:
    return WithTags(row, tag_fks_of(db, row))


def tags_text(db: DBSession, row: SQLModel) -> str:
    """ "billable, urgent", or "" without tags."""

    return ", ".join(tag_names(db, row))


def category_name(db: DBSession, row: Any) -> str | None:
    category = db.get(Category, row.category_fk) if row.category_fk else None
    return category.name if category else None


def labels_json(db: DBSession, row: Any) -> dict[str, Any]:
    """The keys every entity with a Category and Tags adds to its JSON."""

    return {
        "category": category_name(db, row),
        "tag_fks": tag_fks_of(db, row),
        "tags": tag_names(db, row),
    }


def label_details(db: DBSession, row: Any) -> list[tuple[str, str]]:
    """The Category and Tags rows of a `show` panel, as Rich markup."""

    def or_dash(text: str | None) -> str:
        return escape(text) if text else "[dim]—[/dim]"

    return [
        ("Category", or_dash(category_name(db, row))),
        ("Tags", or_dash(tags_text(db, row))),
    ]
