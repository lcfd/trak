from typing import Any

from sqlmodel import Session as DBSession
from sqlmodel import col, func, select

from trak.customers.models import Customer
from trak.labels.links import set_tags

EDITABLE_FIELDS = {"name", "category_fk", "tag_fks"}


def get_customers(db: DBSession, *, name: str | None = None) -> list[Customer]:
    """Customers ordered by name, optionally filtered by exact name."""

    statement = select(Customer).order_by(func.lower(Customer.name), Customer.id)
    if name is not None:
        statement = statement.where(Customer.name == name)
    return list(db.exec(statement))


def check_customer(db: DBSession, name: str, customer_id: int | None = None) -> None:
    """Raise ValueError if a customer can't have this name."""

    if not name:
        raise ValueError("A customer needs a name.")
    if any(c.id != customer_id for c in get_customers(db, name=name)):
        raise ValueError(f'There\'s already a customer called "{name}".')


def create_customer(
    db: DBSession,
    *,
    name: str,
    category_fk: int | None = None,
    tag_fks: list[int] | None = None,
) -> Customer:
    name = name.strip()
    check_customer(db, name)
    customer = Customer(name=name, category_fk=category_fk)
    db.add(customer)
    db.flush()
    set_tags(db, customer, tag_fks or [])
    db.commit()
    db.refresh(customer)
    return customer


def update_customer(db: DBSession, customer: Customer, **changes: Any) -> Customer:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Can't edit {', '.join(sorted(unknown))}.")

    if "name" in changes:
        changes["name"] = changes["name"].strip()
        check_customer(db, changes["name"], customer_id=customer.id)

    if "tag_fks" in changes:
        set_tags(db, customer, changes.pop("tag_fks"))
    for field, value in changes.items():
        setattr(customer, field, value)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def list_customers(
    db: DBSession, *, name: str | None = None, limit: int = 20, offset: int = 0
) -> tuple[list[Customer], int]:
    """
    A page of Customers ordered by name, and the total matching the filter.

    `name` matches case-insensitively anywhere in the name.
    """

    conditions: list[Any] = []
    if name:
        conditions.append(col(Customer.name).icontains(name))

    total = db.exec(select(func.count()).select_from(Customer).where(*conditions)).one()
    statement = (
        select(Customer)
        .where(*conditions)
        .order_by(func.lower(Customer.name), Customer.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.exec(statement)), total
