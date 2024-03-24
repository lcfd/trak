from datetime import datetime, timedelta
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.create.messages.print_new_created_session import print_new_created_session
from trakcli.database.database import add_session
from trakcli.database.models import Record
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.print_with_padding import print_with_padding


def create_session(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    ####################################
    # Add method: by day, and add hours and minutes
    today: Annotated[
        Optional[datetime],
        typer.Option(
            "--today",
            help="For a task happend today, just enter a the time.",
            formats=["%H:%M"],
        ),
    ] = None,
    when: Annotated[
        Optional[datetime],
        typer.Option(
            "--when",
            "-w",
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
    ####################################
    # Start and stop method
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
):
    projects_in_config = get_projects_from_config()

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

    # Check if the project exists
    if not project_id or project_id not in projects_in_config:
        print_missing_project(projects_in_config)
        return

    #
    # Timings
    #

    start_timedate = datetime.today()
    end_timedate = datetime.today()

    # Add method
    ## This comes first because it has priority by design.

    if today or when:
        # Create the start date for the session
        if today:
            start_timedate = start_timedate.replace(
                hour=today.hour, minute=today.minute
            )
        if when:
            start_timedate = when

        end_timedate = start_timedate

        # Add hours and minutes
        if hours or minutes:
            if hours:
                end_timedate = start_timedate + timedelta(hours=hours)
            if minutes:
                end_timedate = start_timedate + timedelta(minutes=minutes)

        else:
            rprint("")
            rprint(
                Panel.fit(
                    title="[red]Missing duration[/red]",
                    renderable=print_with_padding(
                        "You need to provide the duration of the session, in hours or minutes (--minutes or --hours)."
                    ),
                )
            )
            return
    else:
        # Start and end datetimes are probably used
        pass

    # Start and stop method

    if start and end:
        start_timedate = start
        end_timedate = end

    #
    # Create the session
    #

    new_session = Record(
        project=project_id,
        start=start_timedate.isoformat(),
        end=end_timedate.isoformat(),
        billable=billable,
        category=category,
        tag=tag,
    )

    if not dryrun:
        add_session(new_session)
    else:
        rprint("")
        rprint("[bold orange3]DRY RUN")

    print_new_created_session(project_id=project_id, new_session=new_session)
    return

    # else:
    #     # --today and --when parameters are empty
    #     rprint(
    #         Panel(
    #             title="[red]Missing start time[/red]",
    #             renderable=print_with_padding("Use the `--today` or `--when` flag."),
    #         )
    #     )
