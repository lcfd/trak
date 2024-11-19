from typing import NamedTuple


class Work(NamedTuple):
    id: str
    name: str
    time: int
    rate: int
    from_date: str
    to_date: str
    description: str = ""
    done: bool = False
    paid: bool = False
