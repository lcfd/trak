from datetime import datetime
from typing import Annotated, Optional

import typer

from trakcli.projects.database import db_get_project_details
from trakcli.utils.dates import datetime_to_string
from trakcli.utils.messages import print_error, print_success, print_warning
from trakcli.utils.projects_picker import projects_picker
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)
from trakcli.works.models import Work


def create_work(
    work_id: Annotated[
        str,
        typer.Argument(help="The id for the new work."),
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
            help="Budgeted time.",
        ),
    ],
    from_date: Annotated[
        datetime,
        typer.Option(
            "--from",
            help="Start date of the work.",
            formats=["%Y-%m-%dT%H:%M"],
        ),
    ],
    to_date: Annotated[
        datetime,
        typer.Option(
            "--to",
            help="End date of the work.",
            formats=["%Y-%m-%dT%H:%M"],
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
            help="The rate you want to be paid per hour.",
        ),
    ] = 1,
    # Optional
    project_id: Annotated[
        Optional[str],
        typer.Argument(help="The id of the project."),
    ] = None,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    # if project_id in projects_in_config:
    details = db_get_project_details(project_id)

    # Check if project esists
    if details:
        works = get_project_works_from_config(project_id)

        # Check if id already exists
        if works is not None:
            work_ids = [w.id for w in works]
            if work_id in work_ids:
                print_warning(
                    title="This work already exists",
                    text=(
                        f'The id "{work_id}" has already been used in the '
                        f'"{project_id}" project.\n\n'
                        f'You can check ALL the works in the project "{project_id}" '
                        "by using the command:\n"
                        f"trak works list {project_id} --done\n\n"
                        "Use a different value for work_id."
                    ),
                )

                return

        new_work = Work(
            id=work_id,
            name=name,
            time=time,
            rate=rate,
            from_date=datetime_to_string(from_date),
            to_date=datetime_to_string(to_date),
            description=description,
            done=False,
            paid=False,
        )

        if works is not None:
            works.append(new_work)
        else:
            works = [new_work]

        set_project_works_in_config(project_id, works)

        print_success(
            title="Work created",
            text=f"Work [green]{work_id}[/green] created.",
        )

        return
    else:
        print_error(
            title="Error in config",
            text="Error in details file in project's configuration.",
        )

        return
