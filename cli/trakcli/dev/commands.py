import random
from datetime import datetime, timedelta
from random import randrange

import typer
from rich import print as rprint
from rich.padding import Padding
from rich.prompt import Confirm

from trakcli.config.main import CONFIG_FILE_PATH, DEV_DB_FILE_PATH, get_config
from trakcli.database.basic import (
    manage_field_in_json_file,
    overwrite_json_file,
    show_json_file_content,
)
from trakcli.database.database import init_database
from trakcli.database.models import Record
from trakcli.utils.print_with_padding import print_with_padding

app = typer.Typer()


@app.command(
    help="Initialize the development database and activate the development mode."
)
def init():
    """Initialize the development mode."""

    rprint(print_with_padding("▶️  Init dev mode!"))

    confirm_reset_development_database = Confirm.ask(
        """Are you sure you want to init your development database?
⚠️  If you already have one this command will [bold]delete all your data[/bold].""",
        default=True,
    )

    if confirm_reset_development_database:
        # Create the development database (dev_db.json)
        init_database(DEV_DB_FILE_PATH, "[]")

        rprint(
            Padding(
                f"✅ Create development database at {DEV_DB_FILE_PATH}", (2, 0, 0, 0)
            )
        )

        # Add the development parameter to config.json
        manage_field_in_json_file(CONFIG_FILE_PATH, "development", True)

        rprint(f"✅ Add the development parameter to {CONFIG_FILE_PATH}")

        rprint(print_with_padding("⚙️  Here is your new configuration", x=0))
        show_json_file_content(CONFIG_FILE_PATH)

        rprint(print_with_padding("🟢 You are ready to develop on trak!"))


@app.command(help="Toggle the development mode.")
def toggle():
    """Toggle the development mode."""

    CONFIG = get_config()

    if "development" in CONFIG:
        manage_field_in_json_file(
            CONFIG_FILE_PATH, "development", not CONFIG["development"]
        )
        if not CONFIG["development"]:
            rprint(print_with_padding("🟢 You are ready to develop on trak!"))
        else:
            rprint(
                print_with_padding(
                    """👋 You exited the development mode. 

Thanks for your help 🙏"""
                )
            )
    else:
        rprint(
            print_with_padding(
                "🔴 You have to run the [bold]trak dev init[/bold] command."
            )
        )


@app.command(help="Produces mock data for testing purposes.")
def fake(amount: int):
    """Produces mock data for testing purposes."""

    CONFIG = get_config()

    if CONFIG["development"]:
        fake_records = []

        today = datetime.now()
        past_date = today

        projects = ["pokemon", "digimon", "yugioh"]
        categories = ["frontend", "backend", "meeting"]
        tags = ["solo", "multi"]

        for _ in range(0, amount):
            delta = timedelta(hours=randrange(1, 6), minutes=randrange(1, 40))
            delta_plus = timedelta(hours=randrange(1, 3))

            past_date = past_date - delta
            past_date_after = past_date + delta_plus

            fake_records.append(
                Record(
                    project=random.choice(projects),
                    start=past_date.isoformat(),
                    end=past_date_after.isoformat(),
                    category=random.choice(categories),
                    tag=random.choice(tags),
                    billable=random.choice([True, False]),
                )._asdict()
            )

        overwrite_json_file(file_path=DEV_DB_FILE_PATH, content=fake_records)

        rprint(print_with_padding(f"🟢 {amount} fake sessions have been created."))
    else:
        rprint(
            print_with_padding(
                "🔴 This command works only if the developer mode is enabled."
            )
        )


if __name__ == "__main__":
    app()
