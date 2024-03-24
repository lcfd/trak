from typing import Optional

import typer
from rich.console import Console

from trakcli.callbacks import (
    issues_callback,
    report_bug_callback,
    repository_callback,
    version_callback,
    website_callback,
)
from trakcli.config.commands import app as config_app
from trakcli.create import app as create_app
from trakcli.dev.commands import app as dev_app
from trakcli.initialize import initialize_trak
from trakcli.projects.commands import app as projects_app
from trakcli.report import app as report_app
from trakcli.tracker.commands.get_current_session_status import (
    get_current_session_status,
)
from trakcli.tracker.commands.start_tracker import start_tracker
from trakcli.tracker.commands.stop_tracker import stop_tracker
from trakcli.works import app as works_app

console = Console()

app = typer.Typer()

# Initialize trak required files and settings
initialize_trak()

app.command(name="start", help="Start a session.")(start_tracker)
app.command(name="stop", help="Stop the current session.")(stop_tracker)
app.command(name="status", help="Show the status of the current session.")(
    get_current_session_status
)

# Add subcommands
app.add_typer(
    dev_app, name="dev", help="Utils for developers who wants to work on trak."
)
app.add_typer(config_app, name="config", help="Interact with your configuration.")
app.add_typer(projects_app, name="projects", help="Interact with your projects.")
app.add_typer(create_app, name="create", help="Create something in trak.")
app.add_typer(works_app, name="works", help="Interact with your works.")
app.add_typer(report_app, name="report", help="Get useful insights from your records.")


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version.",
        callback=version_callback,
        is_eager=True,
    ),
    website: Optional[bool] = typer.Option(
        None,
        "--website",
        "-w",
        help="Launch the usetrak.com website.",
        callback=website_callback,
        is_eager=True,
    ),
    repository: Optional[bool] = typer.Option(
        None,
        "--repository",
        "-r",
        help="Launch the trak repository.",
        callback=repository_callback,
        is_eager=True,
    ),
    issues: Optional[bool] = typer.Option(
        None,
        "--issues",
        "-i",
        help="Launch the trak issues page on Github.",
        callback=issues_callback,
        is_eager=True,
    ),
    bug: Optional[bool] = typer.Option(
        None,
        "--bug",
        "-b",
        help="Report a bug on Github.",
        callback=report_bug_callback,
        is_eager=True,
    ),
) -> None:
    return
