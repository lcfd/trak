from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    """Who the work is for. It can have a Category and any number of Tags
    (`CustomerTag`)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str | None = None
    category_fk: int | None = Field(default=None, foreign_key="category.id")
