import json
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from trak.config import DB_FILE_PATH

#
# Database operations
#


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
        last_record = parsed_json[-1]
    except IndexError:
        return False

    if last_record["end"] == "":
        return last_record

    return False


def get_current_session():
    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    try:
        last_record = parsed_json[-1]
    except IndexError:
        return False

    if last_record["end"] == "":
        return last_record

    return False


def check_if_database_exists():
    """Check if the json db files exists."""

    return Path.exists(DB_FILE_PATH)


def init_database(p: Path) -> int:
    """Create the application database."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write("[]")
        return 0
    except OSError:
        return 1
