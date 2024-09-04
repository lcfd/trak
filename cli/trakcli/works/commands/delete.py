from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

from trakcli.utils.messages import print_success, print_warning
from trakcli.utils.projects_picker import (
    projects_picker,
)
from trakcli.works.database import (
    get_project_works_from_config_folder,
    set_project_works_in_config_folder,
)


def delete_work(
    work_id: Annotated[str, typer.Argument(help="The id of work.")],
    project_id: Annotated[
        Optional[str], typer.Argument(help="The project id of the work.")
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
    """Delete a work from a project."""

    # Confirm the deletion of a project
    confirm_deletion = Confirm.ask(
        (
            f"\nAre you sure you want to delete the [green]{work_id}[/green] "
            "work from [green]{project_id}[/green] project?"
        ),
        default=False,
    )
    if not confirm_deletion:
        print_warning(
            title="Deletion interrupted", text="Your work will not be deleted."
        )
        raise typer.Abort()

    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    works = get_project_works_from_config_folder(project_id)
    if works is not None:
        filtered_works = [w for w in works if w.id != work_id]

        set_project_works_in_config_folder(project_id, filtered_works)

        print_success(
            title="Success",
            text=f"Work {work_id} successfully deleted from {project_id} project.",
        )

    return
