from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.table import Table

from trakcli.projects.database import get_projects_from_config


def command_project_list(
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """List the projects."""

    projects_in_config = get_projects_from_config(archived)
    combined = {*projects_in_config}

    number_of_projects = len(combined)

    table = Table(
        title=f"{number_of_projects} Projects",
    )

    table.add_column("id", style="green", no_wrap=True)
    table.add_column("from", style="cyan", no_wrap=True)

    for project in projects_in_config:
        table.add_row(project, "config")

    rprint("")
    rprint(table)
