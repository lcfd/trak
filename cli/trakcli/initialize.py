from trakcli.config import (
    init_config,
)
from trakcli.database import init_database
from trakcli.paths import (
    CONFIG_FILE_PATH,
    DB_FILE_PATH,
    PROJECTS_FOLDER_PATH,
)
from trakcli.utils.base_messages import print_success


def initialize_trak():
    """
    Initialize trak required files and configurations at the first start.
    """

    db_initialized = False
    config_initialized = False
    projects_folder_initialized = False
    messages = []

    if not DB_FILE_PATH.is_file():
        try:
            result = init_database(DB_FILE_PATH)
            if result:
                messages.append(f"✅ Database created at {DB_FILE_PATH}.")
                db_initialized = True
            else:
                messages.append(f"❌ Database NOT created at {DB_FILE_PATH}.")
        except Exception as e:
            messages.append(f"❌ Database NOT created at {DB_FILE_PATH}.")
            raise e

    if not CONFIG_FILE_PATH.is_file():
        try:
            result = init_config(CONFIG_FILE_PATH)
            if result:
                messages.append(f"✅ Config file created at {CONFIG_FILE_PATH}.")
                config_initialized = True
            else:
                messages.append(f"❌ Config file NOT created at {CONFIG_FILE_PATH}.")
        except Exception as e:
            messages.append(f"❌ Config file NOT created at {CONFIG_FILE_PATH}.")
            raise e

    if not PROJECTS_FOLDER_PATH.is_dir():
        try:
            PROJECTS_FOLDER_PATH.mkdir(parents=True, exist_ok=True)
            messages.append(f"✅ Projects folder created at {PROJECTS_FOLDER_PATH}.")
            projects_folder_initialized = True
        except Exception as e:
            messages.append(f"❌ Config file NOT created at {CONFIG_FILE_PATH}.")
            raise e

    if db_initialized or config_initialized or projects_folder_initialized:
        print_success(
            title="Trak initalized",
            text=(
                f"{'\n'.join(messages)}"
                "\n\nTrak has created all the files it needs to work."
            ),
        )
    else:
        return
