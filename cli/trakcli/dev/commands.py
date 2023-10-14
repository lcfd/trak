import typer
from rich import print as rprint
from rich.padding import Padding
from rich.prompt import Confirm

from trakcli.config.main import CONFIG, CONFIG_FILE_PATH, DEV_DB_FILE_PATH
from trakcli.database.basic import manage_field_in_json_file, show_json_file_content
from trakcli.database.database import init_database
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


if __name__ == "__main__":
    app()
