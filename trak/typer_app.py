from typing import Optional

from sqlmodel import Session, select
import typer

# from trak.main.annotations import (
#     MainBugOption,
#     MainDocsOption,
#     MainIssuesOption,
#     MainRepositoryOption,
#     MainVersionOption,
#     MainWebsiteOption,
# )
# from trak.configs.commands import app as config_app
# from trak.create import app as create_app
# from trak.delete import app as delete_app
# from trak.dev.commands import app as dev_app
# from trak.edit import app as edit_app
# from trak.doctor import app as doctor_app
# from trak._OLD.initialize import initialize_trak
# from trak.report import app as report_app
# from trak.tracker.commands.get_current_session_status import (
#     command_status,
# )
# from trak.tracker.commands.start_tracker import start_tracker
# from trak.tracker.commands.stop_tracker import stop_tracker


from trak.main.routes import main
from trak.sessions.models import Category

app = typer.Typer(rich_markup_mode="markdown")


app.callback(invoke_without_command=True)(main)


@app.command()
def test(ctx: typer.Context):
    with Session(ctx.obj.get("DB_ENGINE")) as session:
        statement = select(Category)
        categories = session.exec(statement)
        # print(categories)
        for category in categories:
            print(category)


# print(ctx.obj.get("SETTINGS"))


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
# )

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
