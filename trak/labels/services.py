"""Categories and Tags: create, rename, list and delete them (the same rules)."""

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session as DBSession
from sqlmodel import col, delete, func, select, update

from trak.customers.models import Customer
from trak.labels.links import LINKS, tagged_with
from trak.projects.models import Project
from trak.sessions.models import Category, Session, Tag

EDITABLE_FIELDS = {"name"}

Label = Category | Tag


@dataclass(frozen=True)
class Kind:
    """Categories or Tags: what differs between the two."""

    model: type[Category] | type[Tag]
    noun: str
    plural: str

    @property
    def title(self) -> str:
        return self.noun.capitalize()


CATEGORY = Kind(Category, "category", "categories")
TAG = Kind(Tag, "tag", "tags")


def get_labels(db: DBSession, kind: Kind, *, name: str | None = None) -> list[Any]:
    """The labels of `kind` by name, optionally filtered by exact name."""

    model = kind.model
    statement = select(model).order_by(func.lower(model.name), model.id)
    if name is not None:
        statement = statement.where(model.name == name)
    return list(db.exec(statement))


def check_label(
    db: DBSession, kind: Kind, name: str, label_id: int | None = None
) -> None:
    """Raise ValueError if a label of `kind` can't have this name."""

    if not name:
        raise ValueError(f"A {kind.noun} needs a name.")
    if "," in name:
        raise ValueError(f"A {kind.noun} can't have a comma in its name.")
    if any(row.id != label_id for row in get_labels(db, kind, name=name)):
        raise ValueError(f'There\'s already a {kind.noun} called "{name}".')


def create_label(db: DBSession, kind: Kind, *, name: str) -> Any:
    name = name.strip()
    check_label(db, kind, name)
    row = kind.model(name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_label(db: DBSession, kind: Kind, row: Any, **changes: Any) -> Any:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't edit {', '.join(sorted(unknown))}.")

    if "name" in changes:
        changes["name"] = changes["name"].strip()
        check_label(db, kind, changes["name"], label_id=row.id)

    for field, value in changes.items():
        setattr(row, field, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_labels(
    db: DBSession,
    kind: Kind,
    *,
    name: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Any], int]:
    """A page of labels by name, and the total; `name` matches any part."""

    model = kind.model
    conditions: list[Any] = []
    if name:
        conditions.append(col(model.name).icontains(name))

    total = db.exec(select(func.count()).select_from(model).where(*conditions)).one()
    statement = (
        select(model)
        .where(*conditions)
        .order_by(func.lower(model.name), model.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.exec(statement)), total


def session_filter(kind: Kind, row: Any) -> dict[str, int]:
    """The `session_totals` / `list_sessions` filter of the label's Sessions."""

    return {"category_fk" if kind is CATEGORY else "tag_fk": row.id}


def labelled(db: DBSession, kind: Kind, row: Any, model: type) -> list[Any]:
    """The Projects or Customers with this label, by name."""

    if kind is CATEGORY:
        condition = model.category_fk == row.id  # type: ignore[attr-defined]
    else:
        condition = tagged_with(model, row.id)
    statement = select(model).where(condition).order_by(model.name)  # type: ignore[attr-defined]
    return list(db.exec(statement))


def delete_label(db: DBSession, kind: Kind, row: Any) -> None:
    """Delete it, first taking it off every Session, Project and Customer."""

    if kind is CATEGORY:
        for model in (Session, Project, Customer):
            db.exec(
                update(model)  # type: ignore[call-overload]
                .where(model.category_fk == row.id)  # type: ignore[attr-defined]
                .values(category_fk=None)
            )
    else:
        for link, _ in LINKS.values():
            db.exec(delete(link).where(link.tag_fk == row.id))  # type: ignore[call-overload]
    db.delete(row)
    db.commit()
