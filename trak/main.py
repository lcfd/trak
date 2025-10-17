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
from trak.delete import app as delete_app
from trak.dev.commands import app as dev_app
from trak.edit import app as edit_app
from trak.doctor import app as doctor_app
from trak.initialize import initialize_trak
from trak.report import app as report_app
from trak.tracker.commands.get_current_session_status import (
    command_status,
)
from trak.tracker.commands.start_tracker import start_tracker
from trak.tracker.commands.stop_tracker import stop_tracker

app = typer.Typer(rich_markup_mode="markdown")

# Initialize trak required files and settings
# TODO: It may be better to execute it just once

initialize_trak()


@app.callback()
def main(
    version: Optional[bool] = MainVersionOption,
    website: Optional[bool] = MainWebsiteOption,
    repository: Optional[bool] = MainRepositoryOption,
    issues: Optional[bool] = MainIssuesOption,
    bug: Optional[bool] = MainBugOption,
    docs: Optional[bool] = MainDocsOption,
) -> None:
    """
    Keep a record of the time you dedicate to your projects.
    """

    if version or website or repository or issues or bug or docs:
        raise typer.Exit()


# On the actions
# app.command(name="start", help="Start a session.", rich_help_panel="Quick usage")(
#     start_tracker
# )
# app.command(
#     name="stop", help="Stop the current session.", rich_help_panel="Quick usage"
# )(stop_tracker)
# app.command(
#     name="status",
#     help="Show the status of the current session.",
#     rich_help_panel="Quick usage",
# )(command_status)

# Write actions
# app.add_typer(
#     create_app,
#     name="create",
#     help="Create something.",
#     rich_help_panel="Operate on your data",
# )
# app.add_typer(
#     delete_app,
#     name="delete",
#     help="Delete something.",
#     rich_help_panel="Operate on your data",
# )
# app.add_typer(
#     edit_app,
#     name="edit",
#     help="Edit something.",
#     rich_help_panel="Operate on your data",
)

# Read actions
# TODO: TBA
# app.add_typer(
#     xxx,
#     name="find",
#     help="Find something.",
#     rich_help_panel="Read your data",
# )
# app.add_typer(
#     report_app,
#     name="report",
#     help="Get useful insights from your records.",
#     rich_help_panel="Read your data",
# )
#
# # Other
# app.add_typer(
#     config_app,
#     name="config",
#     help="Interact with your configuration.",
#     rich_help_panel="Other",
# )
# app.add_typer(
#     doctor_app,
#     name="doctor",
#     help="Keep your trak instance in shape.",
#     rich_help_panel="Other",
# )
# app.add_typer(
#     dev_app,
#     name="dev",
#     help="Utils for trak developers.",
#     rich_help_panel="Other",
# )
