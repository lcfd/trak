import json
import pathlib
from typing import Annotated, Optional

import typer

from trak._OLD.database import overwrite_json_file
from trak.models import Project
from trak._OLD.paths import PROJECTS_FOLDER_PATH
from trak.utils.base_messages import print_error, print_success
from trak.utils.projects import project_properties_picker, projects_picker
from trak.utils.rich_toolkit import (
    create_rich_toolkit_app,
    get_default_value,
)

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--id",
        help="The id of the project you want to delete.",
    ),
]


def edit_project(id: ProjectIdOption = None):
    """Edit a project."""
    rt_app = create_rich_toolkit_app()

    id = projects_picker(project_id=id, archived=False)
    if not id:
        return

    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / id)

    if not project_path.exists():
        print_error(title="Error", text="This project doesn't exists.")
        return

    details_path = project_path / "details.json"
    if not details_path.exists():
        print_error(
            title="Error", text="This project doesn't hanve the details.json file."
        )
        return

    with open(details_path, "r+") as details_file:
        project_details = json.loads(details_file.read())

        property = project_properties_picker()
        if isinstance(project_details[property], bool):
            value = rt_app.confirm(title=f"Is it {property}?")
        else:
            value = rt_app.input(
                title="Change the current value",
                default=get_default_value(value=project_details[property]),
            )
        confirm = rt_app.confirm(title="Do you want to save the changes?")

        if not confirm:
            return

        project_details[property] = value

        tags = (
            [t.strip() for t in project_details["tags"].split(",")]
            if isinstance(project_details["tags"], str)
            else project_details["tags"]
        )
        categories = (
            [t.strip() for t in project_details["categories"].split(",")]
            if isinstance(project_details["categories"], str)
            else project_details["categories"]
        )

        updated_project = Project(
            name=project_details["name"],
            description=project_details["description"],
            categories=categories,
            tags=tags,
            customer=project_details["customer"],
            rate=int(project_details["rate"]),
            archived=project_details["archived"],
        )

    updated = overwrite_json_file(
        file_path=details_path, content=updated_project._asdict()
    )
    if updated:
        print_success(
            title="Updated",
            text=f"The project {id} has been updated correctly.",
        )
