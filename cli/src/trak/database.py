from datetime import datetime
import json
from pathlib import Path
from typing import NamedTuple

DB_FILE_PATH = Path.home().joinpath(".trak_db.json")


class Record(NamedTuple):
    project: str = ""
    start: str = ""
    end: str = ""
    billable: bool = False
    category: str = ""
    tag: str = ""


def add_track_field(record: Record):
    """..."""

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json.append(record._asdict())

    with open(DB_FILE_PATH, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def stop_track_field():
    """Stop tracking the current project."""

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json[-1]["end"] = datetime.now().isoformat()

    with open(DB_FILE_PATH, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def tracking_already_started():
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()
    parsed_json = json.loads(db_content)

    try:
        last_incomplete_record = parsed_json[-1]
    except IndexError:
        return False

    if last_incomplete_record["end"] == "":
        return last_incomplete_record

    return False


def check_if_database_exists():
    """Check if the json db files exists."""

    return Path.exists(DB_FILE_PATH)


def init_database(db_path: Path) -> int:
    """Create the to-do database."""

    try:
        DB_FILE_PATH.write_text("[]")  # Empty to-do list
        return 0
    except OSError:
        return 1
