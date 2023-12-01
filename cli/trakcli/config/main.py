import json
from pathlib import Path

from trakcli.utils.file_system.get_json_file_content import get_json_file_content


#
# Paths
#

TRAK_FOLDER = Path.home() / ".trak"

DB_FILE_PATH = TRAK_FOLDER / "db.json"
DEV_DB_FILE_PATH = TRAK_FOLDER / "dev_db.json"
CONFIG_FILE_PATH = TRAK_FOLDER / "config.json"


# Read the config at CONFIG_FILE_PATH
def get_config():
    return get_json_file_content(CONFIG_FILE_PATH) if CONFIG_FILE_PATH.is_file() else {}


def get_db_file_path():
    CONFIG = get_config()
    return DEV_DB_FILE_PATH if CONFIG.get("development", False) else DB_FILE_PATH


#
# Configuration helpers
#


def init_config(p: Path) -> int:
    """Init the config file."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as db:
            json.dump(
                {"development": False, "projects": []},
                db,
                indent=2,
                separators=(",", ": "),
            )
        return 0
    except OSError:
        return 1
