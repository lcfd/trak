import pathlib
import shutil

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from trakcli.config.main import (
    TRAK_FOLDER,
    get_db_file_path,
)
from trakcli.projects.database import (
    get_projects_from_config,
    get_projects_from_db,
)
from trakcli.utils.print_with_padding import print_with_padding

app = typer.Typer()


@app.command(help="List your projects.")
def list():
    """List the projects."""

    db_path = get_db_file_path()

    projects_in_db = get_projects_from_db(db_path)
    projects_in_config = get_projects_from_config()
    combined = {*projects_in_db, *projects_in_config}

    number_of_projects = len(combined)

    table = Table(
        title=f"{number_of_projects} Projects",
    )

    table.add_column("id", style="green", no_wrap=True)
    table.add_column("from", style="cyan", no_wrap=True)

    for project in projects_in_config:
        table.add_row(project, "config")

    projects_id_db_only = False
    for project in projects_in_db:
        if project not in projects_in_config:
            projects_id_db_only = True
            table.add_row(project, "database")

    rprint("")
    rprint(table)
    rprint("")
    if projects_id_db_only:
        rprint(
            Panel.fit(
                title="Tip",
                renderable=print_with_padding(
                    (
                        "You have projects that don't exist in configuration.\n"
                        "Plase, run the `trak create project <project-id>` command to configure your project."
                    )
                ),
            )
        )


@app.command(help="Delete a project.")
def delete(project_id: str):
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
