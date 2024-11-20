import random
from datetime import datetime, timedelta
from random import randrange

import typer
from rich import print
from rich.padding import Padding
from rich.prompt import Confirm

from trak.config import (
    CONFIG_FILE_PATH,
    DEV_DB_FILE_PATH,
    get_config,
    get_db_file_path,
)
from trak.database import (
    init_database,
    manage_field_in_json_file,
    overwrite_json_file,
    show_json_file_content,
)
from trak.models import Record
from trak.utils.base_messages import (
    print_error,
    print_info,
    print_success,
    print_with_padding,
)

app = typer.Typer()


@app.command(
    help="Initialize the development database and activate the development mode."
)
def init():
    """Initialize the development mode."""

    print_info(
        title="Init dev mode",
        text="Developer mode is initializing.",
    )

    confirm_reset_development_database = Confirm.ask(
        """Are you sure you want to init your development database?
⚠️  If you already have one this command will [bold]delete all your data[/bold].""",
        default=True,
    )

    if confirm_reset_development_database:
        # Create the development database (dev_db.json)
        init_database(DEV_DB_FILE_PATH, "[]")

        print(
            Padding(
                f"✅ Create development database at {DEV_DB_FILE_PATH}", (2, 0, 0, 0)
            )
        )

        # Add the development parameter to config.json
        manage_field_in_json_file(CONFIG_FILE_PATH, "development", True)

        print(f"✅ Add the development parameter to {CONFIG_FILE_PATH}")

        print(print_with_padding("⚙️  Here is your new configuration", x=0))
        show_json_file_content(CONFIG_FILE_PATH)

        print(print_with_padding("🟢 You are ready to develop on trak!"))
        print_success(
            title="Dev mode ready",
            text="You are ready to develop on trak!",
        )


@app.command(help="Toggle the development mode.")
def toggle():
    """Toggle the development mode."""

    CONFIG = get_config()

    if not CONFIG:
        return

    if isinstance(CONFIG, dict) and "development" in CONFIG:
        manage_field_in_json_file(
            CONFIG_FILE_PATH, "development", not CONFIG["development"]
        )
        if not CONFIG["development"]:
            print_info(
                title="Start dev mode",
                text="You are ready to develop on trak!",
            )
        else:
            print_info(
                title="Stop dev mode",
                text="👋 You exited the development mode.\n\n Thanks for your help 🙏",
            )
    else:
        return


@app.command(help="Produces mock data for testing purposes.")
def fake(amount: int):
    """Produces mock data for testing purposes."""

    CONFIG = get_config()

    if not CONFIG:
        return

    if not isinstance(CONFIG, dict) or not CONFIG.get("development", False):
        print_error(
            title="Dev mode not enabled",
            text="This command works only if the developer mode is enabled.",
        )
        return

    fake_records = []
    now = datetime.now()

    PROJECTS = ["pokemon", "digimon", "yugioh"]
    CATEGORIES = ["frontend", "backend", "meeting"]
    TAGS = ["solo", "multi"]

    for _ in range(0, amount):
        delta = timedelta(hours=randrange(1, 6), minutes=randrange(1, 40))
        delta_plus = timedelta(hours=randrange(1, 3))

        now = now - delta
        today_end = now + delta_plus

        fake_records.append(
            Record(
                project=random.choice(PROJECTS),
                start=now.isoformat(timespec="seconds"),
                end=today_end.isoformat(timespec="seconds"),
                category=random.choice(CATEGORIES),
                tag=random.choice(TAGS),
                billable=random.choice([True, False]),
            )._asdict()
        )

    db_path = get_db_file_path()
    if not db_path:
        print_error(
            title="Dev db is missing or broken",
            text="Try to run the [bold]trak dev init[/bold] command.",
        )
        return

    overwrite_json_file(file_path=db_path, content=fake_records)

    print_success(
        title="Created",
        text=f"{amount} fake sessions have been created.",
    )
