import pathlib
import shutil

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.config.main import TRAK_FOLDER
from trakcli.utils.print_with_padding import print_with_padding


def command_project_delete(project_id: str):
    """Delete a project."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

    rprint("")
    if project_path.exists():
        delete = typer.confirm(
            f"Are you sure you want to delete the {project_id} project?"
        )
        if not delete:
            raise typer.Abort()

        shutil.rmtree(project_path)

        rprint(
            Panel.fit(
                title="[green]Deleted[/green]",
                renderable=print_with_padding(
                    f"The {project_id} has been delete correctly."
                ),
            )
        )
    else:
        rprint(
            Panel.fit(
                title="[red]Error[/red]",
                renderable=print_with_padding(
                    "[red]This project doesn't exists.[/red]"
                ),
            )
        )
