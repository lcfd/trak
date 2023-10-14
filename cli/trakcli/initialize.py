from rich import print as rprint
from rich.panel import Panel

from trakcli.config.main import CONFIG_FILE_PATH, DB_FILE_PATH, init_config
from trakcli.database.database import init_database
from trakcli.utils.print_with_padding import print_with_padding


def initialize_trak():
    """Initialize trak required files and configurations
    at the first start."""

    initialized = False
    messages: list[str] = []

    if not DB_FILE_PATH.is_file():
        initialized = True
        try:
            init_database(DB_FILE_PATH)
            messages.append(f"✅ Database created at {DB_FILE_PATH}.")
        except Exception as e:
            raise e

    if not CONFIG_FILE_PATH.is_file():
        initialized = True
        try:
            init_config(CONFIG_FILE_PATH)
            messages.append(f"✅ Config file created at {CONFIG_FILE_PATH}.")
        except Exception as e:
            raise e

    if initialized:
        rprint(print_with_padding(text="\n".join(messages), y=1))
        initialized_message = "Trak has created all the files it needs to work."
        rprint(
            Panel(
                print_with_padding(initialized_message, y=2),
                title="Trak initalized",
            )
        )
