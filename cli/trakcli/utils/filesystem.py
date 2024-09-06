import json
from pathlib import Path


def read_json_file(file_path: Path) -> list[dict] | dict | None:
    """Read and load the content of a JSON file."""
    with open(file_path, "r") as db:
        json_file_content = db.read()

    try:
        return json.loads(json_file_content)
    except json.decoder.JSONDecodeError:
        return None
