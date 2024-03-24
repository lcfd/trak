from datetime import datetime
from typing import Annotated

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.database.database import add_session, tracking_already_started
from trakcli.database.models import Record
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.utils.print_with_padding import print_with_padding


def start_tracker(
    project: str,
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="The tracked time is billable. Useful in the reporting phase.",
            show_default=True,
        ),
    ] = False,
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
):
    """
    Start tracking a project by name.
    """

    if not project:
        project = typer.prompt("Which project do you want to track?")

    record = tracking_already_started()
    projects_in_config = get_projects_from_config()

    if not record:
        if project in projects_in_config:
            add_session(
                Record(
                    project=project,
                    start=datetime.now().isoformat(),
                    billable=billable,
                    category=category,
                    tag=tag,
                )
            )
            rprint(
                Panel.fit(
                    title="▶️  Start",
                    renderable=print_with_padding(
                        (
                            f"[bold green]{project}[/bold green] started.\n\n"
                            "Have a good session!"
                        )
                    ),
                )
            )
        else:
            print_missing_project(projects_in_config)

            return
    else:
        formatted_start_time = datetime.fromisoformat(record["start"]).strftime(
            "%m/%d/%Y, %H:%M"
        )
        msg = (
            f"Tracking on [bold green]{record['project']}[/bold green] "
            f"already started at {formatted_start_time}"
        )
        rprint(
            Panel.fit(
                title="💬 Already started",
                renderable=print_with_padding(msg),
            )
        )

    return
