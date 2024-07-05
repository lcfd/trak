# Read the config at CONFIG_FILE_PATH
from trakcli.database.filesystem import read_json_file

from .main import CONFIG_FILE_PATH


def get_config():
    return read_json_file(CONFIG_FILE_PATH) if CONFIG_FILE_PATH.is_file() else {}


