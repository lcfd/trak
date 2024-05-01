import json
from typing import Annotated, Optional

import questionary
import typer

from trakcli.projects.database import (
    db_get_project_details,
    db_get_project_details_path,
    get_projects_from_config,
)
from trakcli.projects.messages.print_project_archived_toggle import (
    print_project_archived_toggle,
)
from trakcli.projects.messages.print_project_broken_configuration import (
    print_project_broken_configuration,
)
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.styles_questionary import questionary_style_select


def command_project_archive(project: Annotated[Optional[str], typer.Argument()] = None):
    """Archive a project."""

    projects_in_config = get_projects_from_config(True)

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

    # Provide the list of prjects to the user
    if not project:
        project = questionary.select(
            "Select a project:",
            choices=projects_in_config,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if not project:
            return

    # Check if the project exists
    if not project or project not in projects_in_config:
        print_missing_project(projects_in_config)
        return

    details_path = db_get_project_details_path(project)
    details = db_get_project_details(project)

    if details_path and details:
        # Toggle the value of archived
        details = details._replace(archived=not details.archived)

        with open(details_path, "w") as details_file:
            json.dump(
                details._asdict(),
                details_file,
                indent=2,
                separators=(",", ": "),
            )
        print_project_archived_toggle(project, details.archived)
    else:
        print_project_broken_configuration(project)
        return
