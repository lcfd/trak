import json
from pathlib import Path

from trak.utils.filesystem import read_json_file
from trak.utils.base_messages import print_error

from trak.paths import (
    DB_FILE_PATH,
    DEV_DB_FILE_PATH,
    CONFIG_FILE_PATH,
)

#
# Functions


def init_config(p: Path) -> int:
    """Init the config file."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as config_file:
            json.dump(
                {"development": False, "currency": "€"},
                config_file,
                indent=2,
                separators=(",", ": "),
            )
        return True
    except OSError:
        return False


def get_config():
    return read_json_file(CONFIG_FILE_PATH) if CONFIG_FILE_PATH.is_file() else {}


def get_db_file_path():
    """Get the path of the correct database to use."""

    config = get_config()

    if config and isinstance(config, dict):
        db_path = DEV_DB_FILE_PATH if config.get("development", False) else DB_FILE_PATH

        if db_path.is_file():
            return db_path
        else:
            return None
    else:
        print_error(
            title="Invalid configuration",
            text=(
                f'You should check if "{CONFIG_FILE_PATH}" is in place'
                " and that contains the data in the JSON format."
            ),
        )

        return None
