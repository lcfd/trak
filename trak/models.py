from typing import NamedTuple


class Config(NamedTuple):
    development: bool
    currency: str


class Record(NamedTuple):
    project: str = ""
    start: str = ""
    end: str = ""
    billable: bool = False
    category: str = ""
    tag: str = ""


class Project(NamedTuple):
    id: str
    name: str = ""
    description: str = ""
    categories: list[str] = []
    tags: list[str] = []
    customer: str = ""
    rate: int = 1
    archived: bool = False
