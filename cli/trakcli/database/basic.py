import json
from pathlib import Path
from typing import Optional
from rich import print as rprint


def get_json_file_content(file_path: Path):
    with open(file_path, "r") as db:
        db_content = db.read()

    return json.loads(db_content)


def show_json_file_content(file_path: Path):
    """Show the content of a JSON file."""

    with open(file_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    rprint(parsed_json)


def add_field_to_json_file(
    file_path: Path, field_name: Optional[str], field_value: str | int | float | bool
):
    """Add a field to a JSON file."""

    with open(file_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    if field_name:
        parsed_json[field_name] = field_value

    with open(file_path, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))
