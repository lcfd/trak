import json
from pathlib import Path
import pathlib


from trakcli.config.main import TRAK_FOLDER
from trakcli.config.models import Project


from trakcli.projects.messages.print_project_broken_configuration import (
    print_project_broken_configuration,
)
from trakcli.utils.messages.print_error import print_error


def get_projects_from_db(db_path: Path):
    """Deprecated. Get the projects in the database."""

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    return {record.get("project", "") for record in parsed_json}


def get_projects_from_config(archived: bool | None = False):
    """Get the projects in the config."""

    projects_path = pathlib.Path(TRAK_FOLDER / "projects")

    projects: list[str] = []

    for x in projects_path.iterdir():
        if x.is_dir():
            details_path = x / "details.json"
            with open(details_path, "r") as f:
                details = json.load(f)

                if not details.get("archived") or archived:
                    id = details.get("id", None)
                    if id:
                        projects.append(id)
                    else:
                        print_error(
                            title="Missing id",
                            text=f"The project {str(x)} doesn't have an id.",
                        )

    return projects


def db_get_project_details(project_id: str) -> Project | None:
    """Get a project in the config by id."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

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
        return None


def db_get_project_details_path(project_id: str):
    """Get project config path."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

    if project_path.exists() and project_path.is_dir():
        return project_path / "details.json"
    else:
        return None
