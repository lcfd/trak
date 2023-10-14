import json
from rich.json import JSON
from rich.panel import Panel
import typer

from trakcli.config.main import CONFIG_FILE_PATH
from trakcli.database.basic import get_json_file_content
from rich import print as rprint


app = typer.Typer()


@app.command()
def show():
    """Show the config file."""

    rprint(
        Panel(
            title=f"Your config file {CONFIG_FILE_PATH}",
            renderable=JSON(json.dumps(get_json_file_content(CONFIG_FILE_PATH))),
        )
    )


if __name__ == "__main__":
    app()
