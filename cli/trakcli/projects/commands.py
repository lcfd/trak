import json

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from trakcli.config.main import CONFIG_FILE_PATH, get_config, get_db_file_path
from trakcli.config.models import Project
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


@app.command(help="Create a project.")
def create():
    """Create a project."""

    rprint(
        Panel(
            title="Tips",
            renderable=print_with_padding(
                text="Try to use the exact same name for customers. Grouping will be easier."
            ),
        )
    )

    id = typer.prompt(
        "Id",
    )
    name = typer.prompt(text="Readable name", default="")
    description = typer.prompt("Description", default="")
    categories = typer.prompt(
        "Categories (CSV format)",
        default="",
    )
    tags = typer.prompt("Tags (CSV format)", default="")
    customer = typer.prompt("Customer", default="")
    fare = typer.prompt("Hour rate", default=1, show_default=True)

    if id:
        new_project = Project(
            id=id,
            name=name,
            description=description,
            categories=[c.strip() for c in categories.split(",")]
            if categories != ""
            else [],
            tags=[t.strip() for t in tags.split(",")] if tags != "" else [],
            customer=customer,
            fare=fare,
        )

        config = get_config()

        projects = config.get("projects", [])

        # Check if id is unique
        if new_project.id not in [p.get("id", "") for p in projects]:
            projects.append(new_project._asdict())
            config["projects"] = projects

            with open(CONFIG_FILE_PATH, "w") as open_config:
                json.dump(config, open_config, indent=2, separators=(",", ": "))

            rprint("")
            rprint(
                Panel(
                    title="Success",
                    renderable=print_with_padding(
                        f"[green]Project {id} created.[/green]"
                    ),
                )
            )
        else:
            rprint("")
            rprint(
                Panel(
                    title="Error",
                    renderable=print_with_padding(
                        "[red]This project already exists.[/red]"
                    ),
                )
            )


@app.command(help="Delete a project.")
def delete(id: str):
    """Delete a project."""

    config = get_config()

    projects = config.get("projects", [])

    if id in [p.get("id", "") for p in projects]:
        config["projects"] = [p for p in projects if p.get("id", "") != id]

        with open(CONFIG_FILE_PATH, "w") as open_config:
            json.dump(config, open_config, indent=2, separators=(",", ": "))
            rprint(
                Panel(
                    title="Success",
                    renderable=print_with_padding(
                        f"[green]Project {id} deleted.[/green]"
                    ),
                )
            )
    else:
        rprint(
            Panel(
                title="Error",
                renderable=print_with_padding(
                    "[red]This project doesn't exists.[/red]"
                ),
            )
        )
