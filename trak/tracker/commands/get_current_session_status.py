from datetime import datetime
from typing import Annotated

import typer
from rich import print as rprint
from rich.panel import Panel

from trak.config import get_config
from trak.database import get_current_session
from trak.models import Record
from trak.utils.base_messages import print_with_padding


def get_current_session_status(
    starship: Annotated[
        bool,
        typer.Option(
            "--starship",
            "-s",
            help="Show the output formatted for Starship.",
        ),
    ] = False,
):
    """
    Show the status of the current session.
    """

    CONFIG = get_config()

    current_session = get_current_session()

    if current_session and isinstance(current_session, Record):
        start_datetime = datetime.fromisoformat(current_session.start)
        formatted_start_datetime = start_datetime.strftime("%Y-%m-%d, %H:%M")

        now = datetime.now()
        diff = now - start_datetime

        m, _ = divmod(diff.seconds, 60)
        h, m = divmod(m, 60)

        if starship:
            dev_mode = isinstance(CONFIG, dict) and CONFIG["development"]
            print(
                (
                    f"⏰ {'( DEV MODE) ' if dev_mode else ''}"
                    f"{current_session.project} ⌛ {h}h {m}m"
                )
            )
        else:
            rprint("")
            rprint(
                Panel.fit(
                    title="💬 Current status",
                    renderable=print_with_padding(
                        (
                            f"Project: [green]{current_session.project}[/green]\n\n"
                            f"Started: {formatted_start_datetime}\n"
                            f"Time: [green]{h}h {m}m[/green]"
                        )
                    ),
                )
            )
    else:
        if starship:
            dev_mode = isinstance(CONFIG, dict) and CONFIG["development"]
            print((f"⏰ {'( DEV MODE) ' if dev_mode else ''} " "No active session"))
        else:
            rprint(
                Panel.fit(
                    title="💬 No active session",
                    renderable=print_with_padding(
                        (
                            "There is no ongoing session at the moment.\n\n"
                            "Use the command: trak start <project name>"
                            " to start a new session of work."
                        )
                    ),
                )
            )

    return
