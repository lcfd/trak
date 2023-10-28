from typing import NamedTuple


class Project(NamedTuple):
    id: str
    name: str = ""
    description: str = ""
    categories: list[str] = []
    tags: list[str] = []
    customer: str = ""
    hour_rate: int = 1
