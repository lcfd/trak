from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

from trakcli.utils.messages import print_error, print_success, print_warning
from trakcli.utils.projects_picker import (
    projects_picker,
)
from trakcli.utils.works import change_work_field
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)


def done_work(
    work_id: Annotated[
        str, typer.Argument(help="The id of the work you want to mark as done.")
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
    """Mark a work as done."""

    # Action confirm
    confirm_done = Confirm.ask(
        (
            f"\nAre you sure you want to mark the [green]{work_id}[/green] "
            f"work from [green]{project_id}[/green] project as done?"
        ),
        default=False,
    )
    if not confirm_done:
        print_warning(
            title="Cancelled",
            text=f"The {work_id} work hasn't been marked as done.",
        )
        raise typer.Abort()

    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    works = get_project_works_from_config(project_id)
    if works is not None:
        works_ids = [w.id for w in works]
        if work_id in works_ids:
            modified_works = list(
                map(
                    lambda w: change_work_field(work=w, parameter="done", value=True)
                    if w.id == work_id
                    else w,
                    works,
                )
            )

            set_project_works_in_config(project_id, modified_works)

            print_success(
                title="Success",
                text=(
                    f"Work {work_id} of {project_id} "
                    "project successfully marked as done."
                ),
            )
        else:
            print_error(
                title="[red]The work doesn't exist[/red]",
                text=(
                    "You can create a new work with the command:\n"
                    "trak create work <work_id> -p <project_id> -n <name> -t <hours>"
                    " --from 2024-01-01 --to 2024-02-01"
                ),
            )

            return
