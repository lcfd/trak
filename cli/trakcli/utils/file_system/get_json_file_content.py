import json
from pathlib import Path


def get_json_file_content(file_path: Path):
    with open(file_path, "r") as db:
        json_file_content = db.read()

    return json.loads(json_file_content)
