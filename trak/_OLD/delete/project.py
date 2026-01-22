import pathlib
import shutil
from typing import Annotated, Optional

import typer
from rich import print as rprint

from trak._OLD.database import delete_project_sessions
from trak._OLD.paths import PROJECTS_FOLDER_PATH
from trak.utils.base_messages import print_error, print_success
from trak.utils.projects import projects_picker

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--id",
        help="The id of the project you want to delete.",
    ),
]


def delete_project(id: ProjectIdOption = None):
    """Delete a project."""

    id = projects_picker(project_id=id, archived=False)
    if not id:
        return

    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / id)

    rprint("")
    if not project_path.exists():
        print_error(title="Error", text="This project doesn't exists.")
        return

    if project_path.exists():
        delete = typer.confirm(
            f"Are you sure you want to delete the {id} project?\n"
            "The project's folder and sessions will be deleted."
        )
        if not delete:
            raise typer.Abort()

        delete_project_sessions(id)
        shutil.rmtree(project_path)

        print_success(
            title="Deleted",
            text=f"The project {id} has been delete correctly.",
        )
