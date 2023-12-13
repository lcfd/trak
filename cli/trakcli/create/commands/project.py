import json
import pathlib

import typer
from rich import print as rprint
from rich.panel import Panel

from trakcli.config.main import TRAK_FOLDER
from trakcli.config.models import Project
from trakcli.utils.print_with_padding import print_with_padding


def create_project(
    project_id: str,
):
    rprint("")
    path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)
    files = ["details.json", "works.json", "archived_works.json"]

    path.mkdir(parents=True, exist_ok=True)
    details_path = path / "details.json"
    details_path_exists = details_path.exists()

    # Create files if not exists
    for f in files:
        try:
            with open(path / f, "x") as file:
                file.write("")
        except FileExistsError:
            rprint(f"The file {path / f} already exists, so it won't be created.")

    if not details_path_exists:
        name = typer.prompt(text="Readable name", default="")
        description = typer.prompt("Description", default="")
        categories = typer.prompt(
            "Categories (CSV format)",
            default="",
        )
        tags = typer.prompt("Tags (CSV format)", default="")
        customer = typer.prompt("Customer", default="")
        hour_rate = typer.prompt("Hour rate", default=1, show_default=True)

        if project_id:
            new_project = Project(
                id=project_id,
                name=name,
                description=description,
                categories=[c.strip() for c in categories.split(",")]
                if categories != ""
                else [],
                tags=[t.strip() for t in tags.split(",")] if tags != "" else [],
                customer=customer,
                rate=hour_rate,
            )

            with open(details_path, "w") as details_file:
                json.dump(
                    new_project._asdict(),
                    details_file,
                    indent=2,
                    separators=(",", ": "),
                )

            rprint("")
            rprint(
                Panel.fit(
                    title="[green]Success[/green]",
                    renderable=print_with_padding(f"Project {project_id} created."),
                )
            )

            return
    else:
        rprint("")
        rprint(
            Panel.fit(
                title="[yellow]Already exists[/yellow]",
                renderable=print_with_padding(
                    f"Project {project_id} already has a configuration."
                ),
            )
        )
