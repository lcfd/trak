from pathlib import Path


#
# Paths
#

TRAK_FOLDER = Path.home() / ".trak"

DB_FILE_PATH = TRAK_FOLDER / "db.json"
DEV_DB_FILE_PATH = TRAK_FOLDER / "dev_db.json"
CONFIG_FILE_PATH = TRAK_FOLDER / "config.json"
PROJECTS_FOLDER_PATH = TRAK_FOLDER / "projects/"
