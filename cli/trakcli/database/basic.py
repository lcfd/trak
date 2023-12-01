import json
from pathlib import Path
from rich import print as rprint

from trakcli.config.main import get_db_file_path
from trakcli.utils.file_system.get_json_file_content import get_json_file_content


def get_db_content():
    db_path = get_db_file_path()
    return get_json_file_content(db_path)


def show_json_file_content(file_path: Path):
    """Show the content of a JSON file."""

    with open(file_path, "r") as db:
        json_file_content = db.read()

    parsed_json = json.loads(json_file_content)
    rprint(parsed_json)


def manage_field_in_json_file(
    file_path: Path, field_name: str, field_value: str | int | float | bool
):
    """Manage the content of a single object JSON file."""

    with open(file_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    if field_name:
        parsed_json[field_name] = field_value

    with open(file_path, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def overwrite_json_file(file_path: Path, content: dict | list[dict]):
    """Fill a JSON file with the provided content. It's a complete overwrite."""

    with open(file_path, "w") as db:
        json.dump(content, db, indent=2, separators=(",", ": "))
