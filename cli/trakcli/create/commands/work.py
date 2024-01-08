from datetime import datetime
from typing import Annotated

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.projects.database import get_project_from_config, get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)
from trakcli.works.models import Work


def create_work(
    id: Annotated[
        str,
        typer.Argument(help="The id for the new work."),
    ],
    project_id: Annotated[
        str,
        typer.Option(
            "--project-id",
            "-p",
            help="The id of the project where the new work will be placed.",
        ),
    ],
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="A readable name for the new work.",
        ),
    ],
    time: Annotated[
        int,
        typer.Option(
            "--time",
            "-t",
            help="",
        ),
    ],
    from_date: Annotated[
        datetime,
        typer.Option(
            "--from",
            help="",
            formats=["%Y-%m-%d"],
        ),
    ],
    to_date: Annotated[
        datetime,
        typer.Option(
            "--to",
            help="",
            formats=["%Y-%m-%d"],
        ),
    ],
    description: Annotated[
        str,
        typer.Option(
            "--description",
            "-d",
            help="",
        ),
    ] = "",
    rate: Annotated[
        int,
        typer.Option(
            "--rate",
            "-r",
            help="",
        ),
    ] = 1,
):
    projects_in_config = get_projects_from_config()

    if project_id in projects_in_config:
        details = get_project_from_config(project_id)

        # Check if project esists
        if details:
            works = get_project_works_from_config(project_id)

            # Check if id already exists
            if works is not None:
                work_ids = [w["id"] for w in works]
                if id in work_ids:
                    rprint("")
                    rprint(
                        Panel.fit(
                            title="[yellow]This work id already exists[/yellow]",
                            renderable=print_with_padding(
                                "You should change the id parameter or you can just use the work already in the configuration."
                            ),
                        )
                    )

                    return

            new_work = Work(
                id=id,
                name=name,
                time=time,
                rate=rate,
                from_date=from_date.strftime("%Y-%d-%m"),
                to_date=to_date.strftime("%Y-%d-%m"),
                description=description,
                done=False,
                paid=False,
            )

            if works is not None:
                works.append(new_work._asdict())
            else:
                works = [new_work._asdict()]

            set_project_works_in_config(project_id, works)

            rprint("")
            rprint(
                Panel.fit(
                    title="[green]Work created[/green]",
                    renderable=print_with_padding(f"Work {id} created."),
                )
            )

            return
        else:
            rprint("")
            rprint(
                Panel.fit(
                    title="[red]Error in config[/red]",
                    renderable=print_with_padding(
                        "Error in/with details file in project's configuration."
                    ),
                )
            )

            return
    else:
        print_missing_project(projects_in_config)

        return
