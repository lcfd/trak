from typing import Annotated, Optional

import questionary
import typer
from rich.prompt import Confirm

from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.messages.print_error import print_error
from trakcli.utils.messages.print_success import print_success
from trakcli.utils.messages.print_warning import print_warning
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)

from trakcli.utils.styles_questionary import questionary_style_select


def paid_work(
    work_id: Annotated[str, typer.Argument()],
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """Mark a work of a project as paid."""

    confirm_done = Confirm.ask(
        f"Are you sure you want to mark the [green]{work_id}[/green] work of [green]{project_id}[/green] project as paid?",
        default=False,
    )

    if not confirm_done:
        print_warning(title="Cancelled", text="Paid action cancelled.")
        raise typer.Abort()

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

    works = get_project_works_from_config(project_id)
    if works is not None:
        works_ids = [w["id"] for w in works]
        if work_id in works_ids:
            filtered_works = [
                {**w, "paid": True} if w["id"] == work_id else w for w in works
            ]

            set_project_works_in_config(project_id, filtered_works)

            print_success(
                title="Success",
                text=f"Work {work_id} successfully from {project_id} project marked as paid.",
            )

            return

        else:
            print_error(
                title="The work doesn't exist",
                text=(
                    "You can create a new work with the command:\n"
                    "trak create work <work_id> -p <project_id> -n <name> -t <hours> --from 2024-01-01 --to 2024-02-01"
                ),
            )

            return
