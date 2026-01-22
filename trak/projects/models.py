from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer: int | None = Field(default=None, foreign_key="customer.id")
    name: str
    description: str = ""
    rate: int = 0
    archived: bool = False
