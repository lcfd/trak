from datetime import date

from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """
    Work for a customer, or for yourself.

    `start` and `end` are the days it runs, both included; either can be
    missing (not planned, or open-ended). It can have a Category and any
    number of Tags (`ProjectTag`).
    """

    id: int | None = Field(default=None, primary_key=True)
    customer_fk: int | None = Field(default=None, foreign_key="customer.id")
    name: str
    description: str = ""
    rate: int = 0
    archived: bool = False
    start: date | None = None
    end: date | None = None
    category_fk: int | None = Field(default=None, foreign_key="category.id")
