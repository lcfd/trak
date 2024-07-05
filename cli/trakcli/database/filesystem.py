import json
from pathlib import Path

from rich import print


def read_json_file(file_path: Path) -> list[dict] | dict | None:
    """Read and load the content of a JSON file."""
    with open(file_path, "r") as db:
        json_file_content = db.read()

    try:
        return json.loads(json_file_content)
    except json.decoder.JSONDecodeError:
        return None


def show_json_file_content(file_path: Path):
    """Show the content of a JSON file."""

    with open(file_path, "r") as db:
        json_file_content = db.read()

    parsed_json = json.loads(json_file_content)
    print(parsed_json)


def overwrite_json_file(file_path: Path, content: dict | list[dict]):
    """Fill a JSON file with the provided content. It's a complete overwrite."""

    with open(file_path, "w+") as db:
        json.dump(content, db, indent=2, separators=(",", ": "))
