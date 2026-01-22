import json
import pathlib

from rich_toolkit.menu import Option

from trak._OLD.constants import ALL_PROJECTS
from trak.messages import (
    print_error_no_projects,
    print_missing_project,
    print_project_broken_configuration,
)
from trak.models import Project
from trak._OLD.paths import PROJECTS_FOLDER_PATH
from trak.utils.base_messages import print_error
from trak.utils.rich_toolkit import create_rich_toolkit_app


def get_projects_from_config(archived: bool | None = False):
    """Get the projects in the config."""

    projects_path = pathlib.Path(PROJECTS_FOLDER_PATH)

    projects: list[str] = []

    for x in projects_path.iterdir():
        # Projects are only folders
        if not x.is_dir():
            continue

        project_id = x.name

        # A folder is a project only if contains details.json
        details_path = x / "details.json"
        with open(details_path, "r") as f:
            details = json.load(f)

            if details.get("archived") and not archived:
                continue

            if not project_id:
                print_error(
                    title="Missing id", text=f"The project {str(x)} doesn't have an id."
                )
                continue

            projects.append(project_id)

    return projects


def projects_picker(
    project_id: str | None = None,
    archived: bool | None = False,
    all: bool | None = False,
) -> str | None:
    """Check if the provided project_id is in config."""

    projects_in_config = get_projects_from_config(archived)

    if all:
        projects_in_config.append(ALL_PROJECTS)

    # Check if there are configured projects in config
    if not len(projects_in_config):
        print_error_no_projects()
        return

    if not project_id:
        rt_app = create_rich_toolkit_app()

        projects_options: list[Option] = [
            {"name": project, "value": project} for project in projects_in_config
        ]

        project_id = rt_app.ask(
            title="Select a project:",
            options=projects_options,
            allow_filtering=True,
        )

        if not project_id:
            return

    # project_id isn't in the configuration
    if project_id not in projects_in_config:
        print_missing_project(projects_in_config)
        return
    else:
        return project_id


def project_properties_picker():
    """Returns a Project class property selected by the user."""

    project_propeties_options: list[Option] = [
        {"name": property.capitalize(), "value": property}
        for property in Project.__dict__.keys()
        if not (property.startswith("__") and property.endswith("__"))
        and not property.startswith("_")
    ]

    rt_app = create_rich_toolkit_app()
    return rt_app.ask(
        title="Property", options=project_propeties_options, allow_filtering=True
    )


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


def project_exists(project_id: str):
    """Check if project exists."""

    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / project_id)

    return project_path.exists() and project_path.is_dir()
