import json

import typer
from rich import print as rprint
from rich.json import JSON
from rich.panel import Panel

from trakcli.config.main import CONFIG_FILE_PATH, get_config
from trakcli.database.basic import get_json_file_content

app = typer.Typer()


@app.command()
def show():
    """Show the config file."""

    CONFIG = get_config()

    rprint(
        Panel(
            title=f"Your config file {CONFIG_FILE_PATH}",
            renderable=JSON(json.dumps(CONFIG)),
        )
    )


if __name__ == "__main__":
    app()
