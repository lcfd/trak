from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

from trakcli.utils.works import change_work_field
from trakcli.utils.projects import projects_picker
from trakcli.utils.base_messages import print_error, print_success, print_warning
from trakcli.works.database import (
    get_project_works_from_config_folder,
    set_project_works_in_config_folder,
)


def paid_work(
    work_id: Annotated[
        str, typer.Argument(help="The id of the work you want to mark as paid.")
    ],
    project_id: Annotated[
        Optional[str], typer.Argument(help="The id of the work's project.")
    ] = None,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Consider also archived works.",
        ),
    ] = False,
):
    """Mark a work as paid."""

    # Action confirm
    confirm_paid = Confirm.ask(
        (
            f"\nAre you sure you want to mark the [green]{work_id}[/green] "
            f"work of [green]{project_id}[/green] project as paid?"
        ),
        default=False,
    )

    if not confirm_paid:
        print_warning(
            title="Cancelled",
            text=f"The {work_id} work hasn't been marked as paid.",
        )
        raise typer.Abort()

    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    works = get_project_works_from_config_folder(project_id)
    if works is not None:
        works_ids = [w.id for w in works]
        if work_id in works_ids:
            modified_works = list(
                map(
                    lambda w: change_work_field(work=w, parameter="paid", value=True)
                    if w.id == work_id
                    else w,
                    works,
                )
            )

            set_project_works_in_config_folder(project_id, modified_works)

            print_success(
                title="Success",
                text=(
                    f"Work {work_id} successfully from {project_id}"
                    " project marked as paid."
                ),
            )

            return

        else:
            print_error(
                title="The work doesn't exist",
                text=(
                    "You can create a new work with the command:\n"
                    "trak create work <work_id> -p <project_id> -n <name> -t <hours>"
                    " --from 2024-01-01 --to 2024-02-01"
                ),
            )

            return
