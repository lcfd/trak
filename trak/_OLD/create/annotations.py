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
    Optional[int],
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

#
# Create Session Options

CreateSessionDateOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--date",
        "-d",
        help="Give the date and time of when you have started the session.",
        formats=["%Y-%m-%dT%H:%M"],
    ),
]

CreateSessionHoursOption = Annotated[
    Optional[int],
    typer.Option(
        "--hours",
        "-h",
        help="Hours spent in sessions.",
    ),
]

CreateSessionMinutesOption = Annotated[
    Optional[int],
    typer.Option(
        "--minutes",
        "-m",
        help="Minutes spent in the session.",
    ),
]

CreateSessionStartOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--start",
        "-s",
        help=("The date and time you began the session. "),
        formats=["%Y-%m-%dT%H:%M"],
    ),
]

CreateSessionEndOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--end",
        "-e",
        help=("The date and time you ended the session. "),
        formats=["%Y-%m-%dT%H:%M"],
    ),
]
