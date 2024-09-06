import json
import pathlib

import questionary

from trakcli.messages import (
    print_error_no_projects,
    print_missing_project,
    print_project_broken_configuration,
)
from trakcli.models import Project
from trakcli.paths import PROJECTS_FOLDER_PATH
from trakcli.utils.base_messages import print_error
from trakcli.utils.questionary import questionary_style_select


def get_projects_from_config(archived: bool | None = False):
    """Get the projects in the config."""

    projects_path = pathlib.Path(PROJECTS_FOLDER_PATH)

    projects: list[str] = []

    for x in projects_path.iterdir():
        # Projects are only folders
        if not x.is_dir():
            continue

        # A folder is a project only if contains details.json
        details_path = x / "details.json"
        with open(details_path, "r") as f:
            details = json.load(f)

            if details.get("archived") and not archived:
                continue

            project_id = details.get("id", None)
            if project_id:
                projects.append(project_id)
            else:
                print_error(
                    title="Missing id",
                    text=f"The project {str(x)} doesn't have an id.",
                )

    return projects


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


def db_get_project_details(project_id: str) -> Project | None:
    """Get a project in the config by id."""

    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / project_id)

    if project_path.exists() and project_path.is_dir():
        details_path = project_path / "details.json"
        with open(details_path, "r") as f:
            details = json.load(f)
        try:
            project = Project(**details)
        except Exception:
            print_project_broken_configuration(project_id)
            return None

        return project
    else:
        print_project_broken_configuration(project_id)
        return None


def db_get_project_details_path(project_id: str):
    """Get project config path."""

    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / project_id)

    if project_path.exists() and project_path.is_dir():
        return project_path / "details.json"
    else:
        print_project_broken_configuration(project_id)
        return None
