from datetime import datetime
from typing import Annotated, Optional, TypedDict

import typer
from trak.works.models import Work
from trak.models import Record
from rich.table import Table

BillableOption = Annotated[
    bool,
    typer.Option(
        "--billable",
        "-b",
        help="Consider only the billable records.",
    ),
]

WorksOption = Annotated[
    bool,
    typer.Option(
        "--works",
        help="Show the works related to the project.",
    ),
]

DetailsOption = Annotated[
    bool,
    typer.Option(
        "--details",
        "-d",
        help="Show all sessions that occurred in the chosen period in detail.",
    ),
]

TodayOption = Annotated[
    bool,
    typer.Option(
        "--today",
        help="Consider only today's records.",
    ),
]

YesterdayOption = Annotated[
    bool,
    typer.Option(
        "--yesterday",
        "-y",
        help="Consider only this month's records.",
    ),
]

WeekOption = Annotated[
    bool,
    typer.Option(
        "--week",
        "-w",
        help="Consider only this week's records.",
    ),
]

MonthOption = Annotated[
    bool,
    typer.Option(
        "--month",
        "-m",
        help="Consider only this month's records.",
    ),
]

YearOption = Annotated[
    bool,
    typer.Option(
        "--year",
        help="Consider only this year's records.",
    ),
]

StartOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--start",
        "-s",
        help=(
            "Start date (e.g. 2023-10-08) for the time range. "
            "If --end is not provided, trak will report the data "
            "for the provided date."
        ),
        formats=["%Y-%m-%d"],
    ),
]

EndOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--end",
        "-e",
        help=(
            "End date (e.g. 2023-11-24) for the time range. "
            "Won't work without the start flag."
        ),
        formats=["%Y-%m-%d"],
    ),
]

ArchivedOption = Annotated[
    Optional[bool],
    typer.Option(
        "--archived",
        "-a",
        help="Show archived projects in lists.",
    ),
]


class ProjectData(TypedDict):
    project: str
    details: Table | None
    works: list[Work]
    records: list[Record]
