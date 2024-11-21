from datetime import datetime
from typing import Annotated, Optional, TypedDict

import typer
from trak.works.models import Work
from trak.models import Record
from rich.table import Table

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--project-id",
        help="The id of the project.",
    ),
]

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
        help="Consider only today.",
    ),
]

YesterdayOption = Annotated[
    bool,
    typer.Option(
        "--yesterday",
        "-y",
        help="Consider only yesterday.",
    ),
]

WeekOption = Annotated[
    bool,
    typer.Option(
        "--week",
        "-w",
        help="Consider only the current week.",
    ),
]

MonthOption = Annotated[
    bool,
    typer.Option(
        "--month",
        "-m",
        help="Consider only the current month.",
    ),
]

YearOption = Annotated[
    bool,
    typer.Option(
        "--year",
        help="Consider only the current year.",
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
            "for --start day."
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

WorkIdOption = Annotated[
    Optional[int],
    typer.Option(
        "--id",
        help="The id of the work.",
    ),
]


class ProjectData(TypedDict):
    project: str
    details: Table | None
    works: list[Work]
    records: list[Record]
