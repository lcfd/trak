from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

from trak.database import get_project_works, save_project_works
from trak.utils.base_messages import print_error, print_success
from trak.utils.projects import project_exists, projects_picker
from trak.utils.works import works_picker

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--project-id",
        help="The id of the work's project.",
    ),
]

WorkIdOption = Annotated[
    Optional[int],
    typer.Option(
        "--id",
        help="The id of the work you want to delete.",
    ),
]


def delete_work(
    id: WorkIdOption = None,
    project_id: ProjectIdOption = None,
):
    """Delete a work from a project."""

    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    project_id = projects_picker(project_id=project_id, archived=False)
    if not project_id:
        return

    works_picker_result = works_picker(project_id=project_id, work_id=id)
    if not works_picker_result:
        return

    work_id, work_name = works_picker_result

    # Confirm the deletion
    confirm_deletion = Confirm.ask(
        (
            f"\nAre you sure you want to delete the [green]{work_name} (id {work_id})[/green] "
            f"work from project [green]{project_id}[/green]?"
        ),
        default=False,
    )
    if not confirm_deletion:
        raise typer.Abort()

    works = get_project_works(project_id)
    if not works:
        return

    del works[work_id]

    save_project_works(project_id, works)

    print_success(
        title="Success",
        text=f"Work [green]{work_name} (id {work_id})[/green] successfully deleted from project [green]{project_id}[/green].",
    )
