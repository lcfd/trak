"""
Including a __main__.py module in a Python package enables 
you to run the package as an executable program using the command python -m trak.
"""

from rich.panel import Panel
from trak import cli, __app_name__
from rich import print
from rich.padding import Padding

from trak.config import CONFIG_FILE_PATH, DB_FILE_PATH, init_config
from trak.database import init_database


def print_with_padding(text: str, x: int = 2, y: int = 2):
    return Padding(text, (y, x))


#
# Main function
#


def main():
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
        print(print_with_padding(text="\n".join(messages), y=1))
        initialized_message = "Trak has created all the files it needs to work."
        print(
            Panel(
                print_with_padding(initialized_message, y=2),
                title="Trak initalized",
            )
        )

    cli.app(prog_name=__app_name__)


if __name__ == "__main__":
    main()
