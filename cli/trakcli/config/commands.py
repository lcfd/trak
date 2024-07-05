import json

import typer

from trakcli.config.get_config import get_config
from trakcli.utils.messages import print_info

app = typer.Typer()


@app.command()
def show():
    """Show the config file."""

    CONFIG = get_config()

    print_info(
        title="Your config file",
        text=json.dumps(CONFIG, indent=4),
    )
