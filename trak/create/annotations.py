from datetime import datetime
from typing import Annotated, Optional

import typer


NameOption = Annotated[
    Optional[str],
    typer.Option(
        "--name",
        "-n",
        help="A readable name.",
    ),
]

TimeOption = Annotated[
    Optional[int],
    typer.Option("--time", "-t", help="Budgeted time.", min=0),
]

FromDateOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--from",
        help="Start date of the work.",
        formats=["%Y-%m-%dT%H:%M"],
    ),
]

ToDateOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--to",
        help="End date of the work.",
        formats=["%Y-%m-%dT%H:%M"],
    ),
]

DescriptionOption = Annotated[
    str,
    typer.Option(
        "--description",
        "-d",
        help="",
    ),
]

RateOption = Annotated[
    int,
    typer.Option(
        "--rate",
        "-r",
        help="The rate you want to be paid per hour.",
    ),
]

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--project-id",
        help="The id of the project.",
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
