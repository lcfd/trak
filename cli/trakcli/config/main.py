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
PROJECT_FOLDER_PATH = TRAK_FOLDER / "projects/"


# Read the config at CONFIG_FILE_PATH
def get_config():
    return get_json_file_content(CONFIG_FILE_PATH) if CONFIG_FILE_PATH.is_file() else {}


def get_db_file_path():
    CONFIG = get_config()
    return DEV_DB_FILE_PATH if CONFIG.get("development", False) else DB_FILE_PATH
