from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.utils.messages.print_error import print_error
from trakcli.utils.messages.print_success import print_success
from trakcli.utils.messages.print_warning import print_warning
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)


def done_work(
    work_id: Annotated[str, typer.Argument()],
    project_id: Annotated[
        str,
        typer.Option(
            "--in", "--of", "-p", help="The project's id in which the work is located."
        ),
    ],
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """Mark as done a work of a project."""

    projects = get_projects_from_config(archived)

    if project_id in projects:
        confirm_done = Confirm.ask(
            f"Are you sure you want to mark the [green]{work_id}[/green] work from [green]{project_id}[/green] project as done?",
            default=False,
        )
        if not confirm_done:
            print_warning(
                title="Not marked as done",
                text=f"The {work_id} work hasn't been marked as done.",
            )
            raise typer.Abort()

        works = get_project_works_from_config(project_id)
        if works is not None:
            works_ids = [w["id"] for w in works]
            if work_id in works_ids:
                filtered_works = [
                    {**w, "done": True} if w["id"] == work_id else w for w in works
                ]

                set_project_works_in_config(project_id, filtered_works)

                print_success(
                    title="Success",
                    text=f"Work {work_id} successfully from {project_id} project marked as done.",
                )
            else:
                print_error(
                    title="[red]The work doesn't exist[/red]",
                    text=(
                        "You can create a new work with the command:\n"
                        "trak create work <work_id> -p <project_id> -n <name> -t <hours> --from 2024-01-01 --to 2024-02-01"
                    ),
                )

                return
    else:
        print_missing_project(projects)
