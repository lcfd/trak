import questionary

from trakcli.utils.questionary import questionary_style_select

from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print import print_missing_project, print_error_no_projects


def projects_picker(
    project_id: str | None = None,
    archived: bool | None = False,
    all: bool | None = False,
) -> str | None:
    """Check if the provided project_id is in config."""

    ALL_PROJECTS = "all"

    projects_in_config = get_projects_from_config(archived)

    if all:
        projects_in_config.append(ALL_PROJECTS)

    # Check if there are configured projects in config
    if not len(projects_in_config):
        print_error_no_projects()
        return

    # project_id not provided, show the picker
    # TODO: replace with searchable list
    if not project_id:
        project_id = questionary.select(
            "Select a project:",
            choices=projects_in_config,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if not project_id:
            return

    # project_id isn't in the configuration
    if project_id not in projects_in_config:
        print_missing_project(projects_in_config)
        return

    return project_id
