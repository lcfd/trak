from datetime import datetime
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.database.database import add_session, tracking_already_started
from trakcli.database.models import Record
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.tracker.messages.print_session_already_started import (
    print_session_already_started,
)
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.utils.styles_questionary import questionary_style_select


def start_tracker(
    project: Annotated[Optional[str], typer.Argument()] = None,
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
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """
    Start tracking a project by project_id.
    """

    projects_in_config = get_projects_from_config(archived)

    if not project:
        project = questionary.select(
            "Select a project:",
            choices=projects_in_config,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if not project:
            return

    if project not in projects_in_config:
        print_missing_project(projects_in_config)

        return

    record = tracking_already_started()

    if not isinstance(record, Record):
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
        print_session_already_started(record)

    return
