from datetime import date

from sqlmodel import Field, SQLModel


class Goal(SQLModel, table=True):
    """
    Something to reach on a Project: `hours` of work tracked from `start`
    to `deadline`, both days included.

    More an aim than an obligation: missing it changes nothing.
    """

    id: int | None = Field(default=None, primary_key=True)
    project_fk: int = Field(foreign_key="project.id")
    name: str = ""
    hours: int
    start: date
    deadline: date
