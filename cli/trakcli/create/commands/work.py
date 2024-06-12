from datetime import datetime
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.projects.database import db_get_project_details, get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.datetime_to_string import datetime_to_string
from trakcli.utils.messages.print_error import print_error
from trakcli.utils.messages.print_success import print_success
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)
from trakcli.works.models import Work
from trakcli.utils.styles_questionary import questionary_style_select
from trakcli.utils.messages.print_warning import print_warning


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
    project_id: Annotated[
        Optional[str],
        typer.Argument(help="The id of the project."),
    ] = None,
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
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    projects_in_config = get_projects_from_config(archived)

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

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

    if project_id not in projects_in_config:
        print_missing_project(projects_in_config)

        return

    print(from_date, to_date)

    if project_id in projects_in_config:
        details = db_get_project_details(project_id)

        # Check if project esists
        if details:
            works = get_project_works_from_config(project_id)

            # Check if id already exists
            if works is not None:
                work_ids = [w["id"] for w in works]
                if work_id in work_ids:
                    print_warning(
                        title="This work already exists",
                        text=(
                            f'The id "{work_id}" has already been used in the "{project_id}" project.\n\n'
                            f'You can check ALL the works in the project "{project_id}" by using the command:\n'
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
                works.append(new_work._asdict())
            else:
                works = [new_work._asdict()]

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
    else:
        print_missing_project(projects_in_config)

        return
