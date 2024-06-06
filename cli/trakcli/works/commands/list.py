from typing import Annotated, Optional

import typer

from trakcli.projects.database import db_get_project_details, get_projects_from_config
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.works.database import get_project_works_from_config
from trakcli.works.messages.print_project_works import print_project_works

ALL_PROJECTS = "all"


def list_works(
    project_id: Annotated[str, typer.Argument()] = ALL_PROJECTS,
    done: Annotated[
        bool, typer.Option("--done", "-d", help="Show also done works.")
    ] = False,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """List the works in a project or all of them."""

    if project_id != ALL_PROJECTS:
        details = db_get_project_details(project_id)

        # Check if project esists
        if details:
            works = get_project_works_from_config(project_id)

            if works is not None and done is False:
                works = [w for w in works if w.get("done", False) is False]

            print_project_works(works, project_id)

            return
    else:
        # Show all current projects
        projects_in_config = get_projects_from_config(archived)

        # Check if there are configured projects
        if not len(projects_in_config):
            print_no_projects()
            return

        for project in projects_in_config:
            works = get_project_works_from_config(project)

            if works is not None and len(works):
                print_project_works(works, project)

        return
