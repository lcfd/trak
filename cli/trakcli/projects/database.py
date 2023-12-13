import json
from pathlib import Path
import pathlib

from trakcli.config.main import TRAK_FOLDER


def get_projects_from_db(db_path: Path):
    """Get the projects in the database."""

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    return {record.get("project", "") for record in parsed_json}


def get_projects_from_config():
    """Get the projects in the config."""

    projects_path = pathlib.Path(TRAK_FOLDER / "projects")

    projects = []

    for x in projects_path.iterdir():
        if x.is_dir():
            details_path = x / "details.json"
            with open(details_path, "r") as f:
                details = json.load(f)
                projects.append(details.get("id", "ERROR: No id!"))

    return projects


def get_project_from_config(project_id: str):
    """Get a project in the config by id."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

    if project_path.exists() and project_path.is_dir():
        details_path = project_path / "details.json"
        with open(details_path, "r") as f:
            details = json.load(f)
        return details
    else:
        return None
