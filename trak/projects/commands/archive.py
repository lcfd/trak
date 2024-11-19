import json
from typing import Annotated, Optional

import typer


from trak.messages import print_project_archived_toggle
from trak.utils.projects import (
    db_get_project_details,
    db_get_project_details_path,
    projects_picker,
)


def command_archive_project(
    project_id: Annotated[
        Optional[str], typer.Argument(help="The id of the project you want to archive.")
    ] = None,
):
    """Archive a project."""

    project_id = projects_picker(project_id=project_id, archived=False)
    if not project_id:
        return

    details_path = db_get_project_details_path(project_id)
    if not details_path:
        return

    details = db_get_project_details(project_id)
    if not details:
        return

    # Toggle the value of archived
    details = details._replace(archived=not details.archived)

    with open(details_path, "w") as details_file:
        json.dump(
            details._asdict(),
            details_file,
            indent=2,
            separators=(",", ": "),
        )
    print_project_archived_toggle(project_id, details.archived)
