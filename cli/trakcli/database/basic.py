import json
from pathlib import Path

from trakcli.config.get_db_file_path import get_db_file_path
from trakcli.database.filesystem import read_json_file
from trakcli.database.models import Record


def get_db_content() -> list[Record] | None:
    db_path = get_db_file_path()

    if not db_path:
        return None

    sessions_list = read_json_file(db_path)

    if not sessions_list:
        return None

    try:
        sessions_list = list(map(lambda session: Record(**session), sessions_list))
        return sessions_list
    except Exception:
        return None


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
