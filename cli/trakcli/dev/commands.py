from rich.padding import Padding
import typer
from trakcli.config import CONFIG_FILE_PATH, DEV_DB_FILE_PATH

from trakcli.database.basic import add_field_to_json_file, show_json_file_content
from rich import print as rprint
from rich.prompt import Confirm

from trakcli.database.database import init_database
from trakcli.utils.print_with_padding import print_with_padding

app = typer.Typer()


@app.command()
def init():
    """Manage the development mode."""

    rprint(print_with_padding("▶️  Init dev mode!"))

    confirm_reset_development_database = Confirm.ask(
        """Are you sure you want to init your development database?
⚠️  If you already have one this command will [bold]delete all your data[/bold].""",
        default=True,
    )

    if confirm_reset_development_database:
        # Create the development database (dev_db.json)
        init_database(DEV_DB_FILE_PATH, "{}")

        rprint(
            Padding(
                f"✅ Create development database at {DEV_DB_FILE_PATH}", (2, 0, 0, 0)
            )
        )

        # Add the development parameter to config.json
        add_field_to_json_file(CONFIG_FILE_PATH, "development", True)

        rprint(f"✅ Add the development parameter to {CONFIG_FILE_PATH}")

        rprint(print_with_padding("⚙️  Here is your new configuration", x=0))
        show_json_file_content(CONFIG_FILE_PATH)

        rprint(print_with_padding("🟢 You are ready to develop on trak!"))


if __name__ == "__main__":
    app()
