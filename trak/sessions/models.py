from datetime import datetime

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Session(SQLModel, table=True):
    """
    A Session is the base unit of trak: a span of time, optionally named.

    Everything else is optional: a Session can be associated to a Project,
    to a Customer (directly, or through its Project), a Category and any
    number of Tags (`SessionTag`).

    An active Session is running: it has been started but not stopped yet,
    so it has no `end`. There can be multiple active Sessions at the same time.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    customer_fk: int | None = Field(default=None, foreign_key="customer.id")
    project_fk: int | None = Field(default=None, foreign_key="project.id")
    category_fk: int | None = Field(default=None, foreign_key="category.id")
    start: datetime
    end: datetime | None = None
    active: bool = Field(default=False, index=True)


# Tags: any number on a Session, a Project or a Customer (see `labels/links.py`).


class SessionTag(SQLModel, table=True):
    __tablename__ = "session_tag"  # type: ignore[assignment]

    session_fk: int = Field(foreign_key="session.id", primary_key=True)
    tag_fk: int = Field(foreign_key="tag.id", primary_key=True)


class ProjectTag(SQLModel, table=True):
    __tablename__ = "project_tag"  # type: ignore[assignment]

    project_fk: int = Field(foreign_key="project.id", primary_key=True)
    tag_fk: int = Field(foreign_key="tag.id", primary_key=True)


class CustomerTag(SQLModel, table=True):
    __tablename__ = "customer_tag"  # type: ignore[assignment]

    customer_fk: int = Field(foreign_key="customer.id", primary_key=True)
    tag_fk: int = Field(foreign_key="tag.id", primary_key=True)
