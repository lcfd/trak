import json
from pathlib import Path


def get_projects_from_db(db_path: Path):
    """Get the projects in the database."""

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    return {record.get("category", "") for record in parsed_json}


def get_projects_from_config(config):
    """Get the projects in the config."""

    projects = config.get("projects", [])

    return [p.get("id", "ERROR: No id!") for p in projects]
