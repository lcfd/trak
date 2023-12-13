from typing import Annotated
from rich.panel import Panel
from trakcli.projects.utils.print_missing_project import print_missing_project
from rich.prompt import Confirm


import typer
from rich import print as rprint

from trakcli.projects.database import get_projects_from_config
from trakcli.works.database import (
    get_project_works_from_config,
    set_project_works_in_config,
)


def delete_work(
    work_id: Annotated[str, typer.Argument()],
    project_id: Annotated[
        str,
        typer.Option(
            "--in", "--of", "-p", help="The project's id in which the work is located."
        ),
    ],
):
    """Delete a work from a project."""

    projects = get_projects_from_config()

    if project_id in projects:
        delete = Confirm.ask(
            f"Are you sure you want to delete the [green]{work_id}[/green] work from [green]{project_id}[/green] project?",
            default=False,
        )
        if not delete:
            rprint("")
            rprint("[yellow]Not deleting.[/yellow]")
            raise typer.Abort()

        works = get_project_works_from_config(project_id)
        if works is not None:
            filtered_works = [w for w in works if w["id"] != work_id]

            set_project_works_in_config(project_id, filtered_works)

            rprint("")
            rprint(
                Panel.fit(
                    title="[green]Success[/green]",
                    renderable=f"Work {work_id} successfully deleted from {project_id} project.",
                )
            )
    else:
        print_missing_project(projects)
