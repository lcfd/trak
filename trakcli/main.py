from typing import Optional

import typer

from trakcli.annotations import (
    MainBugOption,
    MainDocsOption,
    MainIssuesOption,
    MainRepositoryOption,
    MainVersionOption,
    MainWebsiteOption,
)
from trakcli.configs.commands import app as config_app
from trakcli.create import app as create_app
from trakcli.dev.commands import app as dev_app
from trakcli.initialize import initialize_trak
from trakcli.projects import app as projects_app
from trakcli.report import app as report_app
from trakcli.tracker.commands.get_current_session_status import (
    get_current_session_status,
)
from trakcli.tracker.commands.start_tracker import start_tracker
from trakcli.tracker.commands.stop_tracker import stop_tracker
from trakcli.works import app as works_app

app = typer.Typer()

# Initialize trak required files and settings
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
