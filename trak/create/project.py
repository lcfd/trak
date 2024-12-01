import json
import pathlib

import typer
from rich import print as rprint

from trak.create.annotations import NameOption, ProjectIdOption
from trak.models import Project
from trak.paths import PROJECTS_FOLDER_PATH
from trak.utils.base_messages import print_success, print_warning
from trak.utils.rich_toolkit import rich_toolkit_input


def create_project(
    project_id: ProjectIdOption = None,
    name: NameOption = None,
):
    new_project_id = None
    if isinstance(project_id, str):
        new_project_id = project_id
    else:
        while not isinstance(new_project_id, str):
            new_project_id = rich_toolkit_input(
                title="Project id? It will be also the name of the folder."
            )

    path = pathlib.Path(PROJECTS_FOLDER_PATH / new_project_id)
    files_to_create = ["details.json", "works.json", "archived_works.json"]

    path.mkdir(parents=True, exist_ok=True)
    details_path = path / "details.json"
    details_path_exists = details_path.exists()

    # Create files if not exists
    for f in files_to_create:
        try:
            with open(path / f, "x") as file:
                file.write("")
        except FileExistsError:
            rprint(f"The file {path / f} already exists, so it won't be created.")

    if details_path_exists:
        print_warning(
            title="Already exists",
            text=f"Project {new_project_id} already has a configuration.",
        )
        return

    new_project_name = ""
    if isinstance(name, str) and len(name):
        new_project_name = name
    else:
        while not isinstance(new_project_name, str) or not len(new_project_name):
            new_project_name = typer.prompt("Readable name", default="")

    description = typer.prompt("Description", default="")
    categories = typer.prompt(
        "Categories (CSV format)",
        default="",
    )
    tags = typer.prompt("Tags (CSV format)", default="")
    customer = typer.prompt("Customer", default="")
    hour_rate = typer.prompt("Hour rate", default=1, show_default=True)
    archived = typer.prompt("Archived", default=False, show_default=True)

    if new_project_id:
        new_project = Project(
            name=new_project_name,
            description=description,
            categories=[c.strip() for c in categories.split(",")]
            if categories != ""
            else [],
            tags=[t.strip() for t in tags.split(",")] if tags != "" else [],
            customer=customer,
            rate=hour_rate,
            archived=archived,
        )

        with open(details_path, "w") as details_file:
            json.dump(
                new_project._asdict(),
                details_file,
                indent=2,
                separators=(",", ": "),
            )

        print_success(text=f"Project {new_project_id} created.")
