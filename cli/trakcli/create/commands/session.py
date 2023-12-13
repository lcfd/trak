from datetime import datetime, timedelta
from typing import Annotated, Optional
from trakcli.projects.utils.print_missing_project import print_missing_project

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.database.database import add_session
from trakcli.database.models import Record
from trakcli.projects.database import get_projects_from_config
from trakcli.utils.print_with_padding import print_with_padding


def create_session(
    project_id: str,
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
            help="Last name of person to greet.",
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
    dryrun: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Check the session you are about to create, without save it.",
        ),
    ] = False,
):
    # Check if the project exists
    projects_in_config = get_projects_from_config()
    if len(projects_in_config):
        if project_id in projects_in_config:
            # Check if today or when is passed
            start_timedate = datetime.today()
            if today or when:
                # Create the start date for the session
                if today:
                    now = datetime.today()
                    today_time = today.time()
                    start_timedate = now.replace(
                        hour=today_time.hour, minute=today_time.minute
                    )
                if when:
                    start_timedate = when

                end_timedate = start_timedate
                if hours or minutes:
                    if hours:
                        end_timedate = end_timedate + timedelta(hours=hours)
                    if minutes:
                        end_timedate = end_timedate + timedelta(minutes=minutes)

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
                        rprint("")
                        rprint("✅ Session created.")

                    rprint("")
                    rprint(
                        Panel.fit(
                            title=project_id,
                            renderable=print_with_padding(
                                (
                                    f"start: {new_session.start}\n"
                                    f"end: {new_session.end}\n"
                                    f"billable: {new_session.billable}\n"
                                    f"category: {new_session.category}\n"
                                    f"tag: {new_session.tag}"
                                )
                            ),
                        )
                    )

                    return
            else:
                rprint(
                    Panel(
                        title="[red]Missing start time[/red]",
                        renderable=print_with_padding(
                            "Use the `--today` or `--when` flag."
                        ),
                    )
                )
        else:
            print_missing_project(projects_in_config)
            return
    else:
        rprint(projects_in_config)
