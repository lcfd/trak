from typing import Annotated, Optional

import typer

from trak.utils.base_messages import print_error
from trak.utils.projects import (
    db_get_project_details,
    get_projects_from_config,
    projects_picker,
)
from trak.works.database import get_project_works_from_config_folder
from trak.works.messages import print_project_works

ALL_PROJECTS = "all"


def list_works(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    done: Annotated[
        bool, typer.Option("--done", "-d", help="Show done works in lists.")
    ] = False,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived works in lists.",
        ),
    ] = False,
):
    """List the works in a project or all of them."""

    project_id = projects_picker(project_id=project_id, archived=archived, all=True)

    if not project_id:
        return

    if project_id != ALL_PROJECTS:
        details = db_get_project_details(project_id)

        if details:
            works = get_project_works_from_config_folder(project_id)

            # Filter by --done
            if works is not None and done is False:
                works = [w for w in works if not w.done]

            print_project_works(works, project_id)
        else:
            print_error(
                title="Project's details",
                text=(
                    f"There is something wrong with the details of"
                    " the project you have chosen.\n\n"
                    f'Check the "{project_id}/details.json '
                    "file in your configuration."
                ),
            )
    else:
        # Show all current projects
        projects_in_config = get_projects_from_config(archived)

        # Check if there are configured projects
        if not len(projects_in_config):
            return

        for project_id in projects_in_config:
            works = get_project_works_from_config_folder(project_id)

            # Filter by --done
            if works is not None and done is False:
                works = [w for w in works if not w.done]

            if works is not None and len(works):
                print_project_works(works, project_id)
