from typing import NamedTuple


class Record(NamedTuple):
    project: str = ""
    start: str = ""
    end: str = ""
    billable: bool = False
    category: str = ""
    tag: str = ""


# SPOILER

# class Project(NamedTuple):
#     short_name: str
#     name: str = ""
#     description: str = ""
#     customer: str = ""
#     hour_rate: str = ""
