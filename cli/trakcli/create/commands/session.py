from datetime import datetime
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint

from trakcli.create.create_sessions_methods import add_method, sub_method
from trakcli.create.messages.print_missing_duration import print_missing_duration
from trakcli.create.messages.print_missing_timings_error import (
    print_missing_timings_error,
)
from trakcli.create.messages.print_new_created_session import print_new_created_session
from trakcli.database.database import add_session
from trakcli.database.models import Record
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.styles_questionary import questionary_style_select


def create_session(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    date: Annotated[
        Optional[datetime],
        typer.Option(
            "--date",
            "-d",
            help="Give the date and time of when you have started the session.",
            formats=["%Y-%m-%dT%H:%M"],
        ),
    ] = None,
    hours: Annotated[
        Optional[int],
        typer.Option(
            "--hours",
            "-h",
            help="Hours spent in sessions.",
        ),
    ] = None,
    minutes: Annotated[
        Optional[int],
        typer.Option(
            "--minutes",
            "-m",
            help="Minutes spent in the session.",
        ),
    ] = None,
    start: Annotated[
        Optional[datetime],
        typer.Option(
            "--start",
            "-s",
            help="The date and time you began the session. Incompatible with --when/--today.",
            formats=["%Y-%m-%dT%H:%M"],
        ),
    ] = None,
    end: Annotated[
        Optional[datetime],
        typer.Option(
            "--end",
            "-e",
            help="The date and time you ended the session. Incompatible with --when/--today.",
            formats=["%Y-%m-%dT%H:%M"],
        ),
    ] = None,
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
    #
    # Project checking
    projects_in_config = get_projects_from_config(archived)

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

    # Provide the list of prjects to the user
    if not project_id:
        project_id = questionary.select(
            "Select a project:",
            choices=projects_in_config,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if not project_id:
            return

    # Check if the project exists
    if not project_id or project_id not in projects_in_config:
        print_missing_project(projects_in_config)
        return
    # End project checking
    #

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
        add_session(new_session)
    else:
        rprint("\n[bold orange3] 󰙨 DRY RUN[bold orange3]")

    #
    # Visual output
    print_new_created_session(project_id=project_id, new_session=new_session)

    return
