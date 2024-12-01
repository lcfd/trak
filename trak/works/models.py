from typing import NamedTuple


class Work(NamedTuple):
    name: str
    time: int
    rate: int
    from_date: str
    to_date: str
    description: str = ""
    done: bool = False
    paid: bool = False


WORK_FIELDS_TYPES = {
    "name": "str",
    "time": "int",
    "rate": "int",
    "from_date": "datetime",
    "to_date": "datetime",
    "description": "str",
    "done": "bool",
    "paid": "bool",
}
