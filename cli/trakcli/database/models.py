from typing import NamedTuple


class Record(NamedTuple):
    project: str = ""
    start: str = ""
    end: str = ""
    billable: bool = False
    category: str = ""
    tag: str = ""
