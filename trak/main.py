from typing import Optional

import typer

from trak.annotations import (
    MainBugOption,
    MainDocsOption,
    MainIssuesOption,
    MainRepositoryOption,
    MainVersionOption,
    MainWebsiteOption,
)
from trak.configs.commands import app as config_app
from trak.create import app as create_app
from trak.dev.commands import app as dev_app
from trak.initialize import initialize_trak
from trak.projects import app as projects_app
from trak.report import app as report_app
from trak.tracker.commands.get_current_session_status import (
    get_current_session_status,
)
from trak.tracker.commands.start_tracker import start_tracker
from trak.tracker.commands.stop_tracker import stop_tracker
from trak.works import app as works_app
from trak.doctor import app as doctor_app

app = typer.Typer()

# Initialize trak required files and settings
# TODO: It may be better to execute it just once

initialize_trak()


#
# Add subcommands
app.add_typer(config_app, name="configs", help="Interact with your configuration.")
app.add_typer(projects_app, name="projects", help="Interact with your projects.")
app.add_typer(works_app, name="works", help="Interact with your works.")

#
# Actions routes
app.command(name="start", help="Start a session.")(start_tracker)
app.command(name="stop", help="Stop the current session.")(stop_tracker)
app.command(name="status", help="Show the status of the current session.")(
    get_current_session_status
)
app.add_typer(create_app, name="create", help="Create something in trak.")
app.add_typer(report_app, name="report", help="Get useful insights from your records.")
app.add_typer(
    dev_app, name="dev", help="Utils for developers who wants to work on trak."
)
app.add_typer(doctor_app, name="doctor", help="Utils for keeping trak in shape.")


@app.callback()
def main(
    version: Optional[bool] = MainVersionOption,
    website: Optional[bool] = MainWebsiteOption,
    repository: Optional[bool] = MainRepositoryOption,
    issues: Optional[bool] = MainIssuesOption,
    bug: Optional[bool] = MainBugOption,
    docs: Optional[bool] = MainDocsOption,
) -> None:
    return
