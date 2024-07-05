from trakcli.config.get_config import get_config
from trakcli.config.main import CONFIG_FILE_PATH, DB_FILE_PATH, DEV_DB_FILE_PATH
from trakcli.utils.messages import print_error


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
