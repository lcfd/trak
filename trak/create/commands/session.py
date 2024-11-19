from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print

from trak.create.create_session_methods import add_method, sub_method
from trak.create.messages import (
    print_missing_duration,
    print_missing_timings_error,
    print_new_created_session,
)
from trak.database import add_session
from trak.models import Record
from trak.utils.base_messages import print_error
from trak.utils.projects import projects_picker

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
        help=(
            "The date and time you began the session. "
            "Incompatible with --when/--today."
        ),
        formats=["%Y-%m-%dT%H:%M"],
    ),
]

CreateSessionEndOption = Annotated[
    Optional[datetime],
    typer.Option(
        "--end",
        "-e",
        help=(
            "The date and time you ended the session. "
            "Incompatible with --when/--today."
        ),
        formats=["%Y-%m-%dT%H:%M"],
    ),
]


def create_session(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    date: CreateSessionDateOption = None,
    hours: CreateSessionHoursOption = None,
    minutes: CreateSessionMinutesOption = None,
    start: CreateSessionStartOption = None,
    end: CreateSessionEndOption = None,
    ####################################
    # Properties
    category: Annotated[
        str,
        typer.Option(
            "--category",
            "-c",
            help="Add a category to the tracked time. Useful in the reporting phase.",
        ),
    ] = "",
    tag: Annotated[
        str,
        typer.Option(
            "--tag",
            "-t",
            help="Add a tag to the tracked time. Useful in the reporting phase.",
        ),
    ] = "",
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="The project is billable.",
        ),
    ] = False,
    ####################################
    # Meta
    dryrun: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "--dryrun",
            help="Check the session you are about to create, without save it.",
        ),
    ] = False,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """Create a session."""

    project_id = projects_picker(project_id=project_id, archived=archived, all=True)
    if not project_id:
        return

    #
    # Timings
    start_timedate = datetime.today()
    end_timedate = datetime.today()

    if date:
        #
        # Add method
        #
        # Medium fast, for when user remember when has started the session
        if not hours and not minutes:
            # There must be at least hours or minutes if today or date are used
            print_missing_duration()

            return

        start_timedate, end_timedate = add_method(date, hours, minutes)

    elif hours or minutes:
        #
        # Sub method
        #
        ## Fast, usually good for when a session just finished
        start_timedate, end_timedate = sub_method(hours, minutes)

    elif start and end:
        #
        # Precise method
        #
        ## Slow, but useful for precise or automated insertions
        start_timedate = start
        end_timedate = end

    else:
        # No data from user
        print_missing_timings_error()

        return

    #
    # Create the session
    new_session = Record(
        project=project_id,
        start=start_timedate.isoformat(),
        end=end_timedate.isoformat(),
        billable=billable,
        category=category,
        tag=tag,
    )

    #
    # Handle dryrun
    if not dryrun:
        if add_session(new_session):
            print_new_created_session(project_id=project_id, new_session=new_session)
        else:
            print_error(title="Session not created", text="Check your configuration.")
    else:
        print("\n[bold orange3] 󰙨 DRY RUN[bold orange3]")

    return
