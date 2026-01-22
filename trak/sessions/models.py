from datetime import datetime
from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project: int | None = Field(default=None, foreign_key="project.id")
    category: int | None = Field(default=None, foreign_key="category.id")
    tag: int | None = Field(default=None, foreign_key="tag.id")
    start: datetime
    end: datetime


class RunningSession(SQLModel, table=True):
    """
    A RunningSession is a Session that has been started but not finished.
    There can be multiple RunningSession at the same time.

    You can also consider it as a temporary Session.
    """

    id: int | None = Field(default=None, primary_key=True)
    project: int | None = Field(default=None, foreign_key="project.id")
    category: int | None = Field(default=None, foreign_key="category.id")
    tag: int | None = Field(default=None, foreign_key="tag.id")
    start: datetime
