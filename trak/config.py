"""Configuration file for settings that user can't change."""

import os
from pathlib import Path

# Metadata
APP_NAME = "trak"
VERSION = "0.0.6"
WEBSITE = "https://usetrak.com"
GIT_REPOSITORY = "https://github.com/lcfd/trak"
DOCS = "https://docs.usetrak.com"

# Paths
# Follow the XDG Base Directory spec: settings in ~/.config, data in ~/.local/share.
CONFIG_FOLDER = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_NAME
)
DATA_FOLDER = (
    Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / APP_NAME
)
DB_PATH = DATA_FOLDER / "db.sqlite3"
DB_DEV_PATH = DATA_FOLDER / "dev_db.sqlite3"
SETTINGS_FILE_PATH = CONFIG_FOLDER / "settings.toml"

# Development mode
# Enabled with `TRAK_DEV=1` or `development = true` in settings.toml.
# The environment variable wins, so `TRAK_DEV=0` disables it for one command.
DEV_ENV_VAR = "TRAK_DEV"


# DB_FILE_PATH = TRAK_FOLDER / "db.json"
# DEV_DB_FILE_PATH = TRAK_FOLDER / "dev_db.json"
# CONFIG_FILE_PATH = TRAK_FOLDER / "config.json"
# PROJECTS_FOLDER_PATH = TRAK_FOLDER / "projects/"

# import json
# from pathlib import Path
#
# from trak.utils.filesystem import read_json_file
# from trak.utils.base_messages import print_error
#
# from trak.paths import (
#     DB_FILE_PATH,
#     DEV_DB_FILE_PATH,
#     CONFIG_FILE_PATH,
#     PROJECTS_FOLDER_PATH,
# )
#
# #
# # Functions
#
#
# def init_config(p: Path) -> int:
#     """Init the config file."""
#
#     try:
#         p.parent.mkdir(parents=True, exist_ok=True)
#         with p.open("w", encoding="utf-8") as config_file:
#             json.dump(
#                 {"development": False, "currency": "€"},
#                 config_file,
#                 indent=2,
#                 separators=(",", ": "),
#             )
#         return True
#     except OSError:
#         return False
#
#
# def get_config():
#     return read_json_file(CONFIG_FILE_PATH) if CONFIG_FILE_PATH.is_file() else {}
#
#
# def get_db_file_path():
#     """Get the path of the correct database to use."""
#
#     config = get_config()
#
#     if config and isinstance(config, dict):
#         db_path = DEV_DB_FILE_PATH if config.get("development", False) else DB_FILE_PATH
#
#         if db_path.is_file():
#             return db_path
#         else:
#             return None
#     else:
#         print_error(
#             title="Invalid configuration",
#             text=(
#                 f'You should check if "{CONFIG_FILE_PATH}" is in place'
#                 " and that contains the data in the JSON format."
#             ),
#         )
#
#         return None
#
#
# def get_works_path(project_id: str):
#     project_path = Path(PROJECTS_FOLDER_PATH / project_id)
#
#     if not project_path.exists() or not project_path.is_dir():
#         return None
#
#     return project_path / "works.json"
