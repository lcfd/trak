from typing import Annotated, Optional

import typer

from trakcli.projects.database import db_get_project_details, get_projects_from_config
from trakcli.projects.utils.get_existent_projects import get_existent_projects
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.messages.print_error import print_error
from trakcli.works.database import get_project_works_from_config
from trakcli.works.messages.print_project_works import print_project_works

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
    if not project_id:
        project_id = get_existent_projects(all_option=True, archived=archived)

    if project_id:
        if project_id != ALL_PROJECTS:
            details = db_get_project_details(project_id)

            if details:
                works = get_project_works_from_config(project_id)

                if works is not None and done is False:
                    works = [w for w in works if w.done is False]

                print_project_works(works, project_id)
            else:
                print_error(
                    title="Project's details",
                    text=(
                        f"There is something wrong with the details of the project you have chosen.\n\n"
                        f'Check the "{project_id}/details.json" file in your configuration.'
                    ),
                )
        else:
            # Show all current projects
            projects_in_config = get_projects_from_config(archived)

            # Check if there are configured projects
            if not len(projects_in_config):
                print_no_projects()
            else:
                for project in projects_in_config:
                    works = get_project_works_from_config(project)

                    if works is not None and len(works):
                        print_project_works(works, project)

    return
