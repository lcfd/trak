import questionary
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.utils.styles_questionary import questionary_style_select

ALL_PROJECTS = "all"


def get_existent_projects(all_option: bool | None, archived: bool | None):
    projects_in_config = get_projects_from_config(archived)

    if all_option:
        projects_in_config.append(ALL_PROJECTS)

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

    project = questionary.select(
        "Select a project:",
        choices=projects_in_config,
        pointer="• ",
        show_selected=True,
        style=questionary_style_select,
    ).ask()

    if not project:
        return

    return project
