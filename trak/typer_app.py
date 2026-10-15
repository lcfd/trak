import typer
from sqlmodel import Session, select

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
# from trak._OLD.initialize import initialize_trak
# from trak.report import app as report_app
# from trak.tracker.commands.get_current_session_status import (
#     command_status,
# )
from trak.customers import commands as customers
from trak.customers import listing as customers_listing
from trak.doctor import doctor_command
from trak.entities import entity_app
from trak.goals import commands as goals
from trak.goals import listing as goals_listing
from trak.main.routes import main
from trak.projects import commands as projects
from trak.projects import listing as projects_listing
from trak.sessions import creating as sessions_creating
from trak.sessions import details as sessions_details
from trak.sessions import listing as sessions_listing
from trak.sessions.commands import start, stop
from trak.sessions.editing import edit_command
from trak.sessions.models import Category

app = typer.Typer(rich_markup_mode="markdown")


app.callback(invoke_without_command=True)(main)


@app.command(hidden=True)
def test(ctx: typer.Context):
    with Session(ctx.obj.get("DB_ENGINE")) as session:
        statement = select(Category)
        categories = session.exec(statement)
        # print(categories)
        for category in categories:
            print(category)


# print(ctx.obj.get("SETTINGS"))


# On the actions
app.command(name="start", help="Start a session.", rich_help_panel="Quick usage")(start)
app.command(
    name="stop", help="Stop the active session.", rich_help_panel="Quick usage"
)(stop)
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

# Your data: `trak <entities> [ID | COMMAND]`
sessions_app = entity_app("sessions")
sessions_app.command(name="list", help="List sessions, newest first.")(
    sessions_listing.list_command
)
sessions_app.command(name="show", help="Show a session.")(sessions_details.show_command)
sessions_app.command(name="create", help="Add a past session.")(
    sessions_creating.create_command
)
sessions_app.command(name="edit", help="Edit a session.")(edit_command)
app.add_typer(sessions_app, name="sessions", rich_help_panel="Your data")

projects_app = entity_app("projects")
projects_app.command(name="list", help="List projects by name.")(
    projects_listing.list_command
)
projects_app.command(name="show", help="Show a project.")(projects.show_command)
projects_app.command(name="create", help="Create a project.")(projects.create_command)
projects_app.command(name="edit", help="Edit a project.")(projects.edit_command)
projects_app.command(name="report", help="Report the time tracked on a project.")(
    projects.report_command
)
app.add_typer(projects_app, name="projects", rich_help_panel="Your data")

customers_app = entity_app("customers")
customers_app.command(name="list", help="List customers by name.")(
    customers_listing.list_command
)
customers_app.command(name="show", help="Show a customer.")(customers.show_command)
customers_app.command(name="create", help="Create a customer.")(
    customers.create_command
)
customers_app.command(name="edit", help="Edit a customer.")(customers.edit_command)
app.add_typer(customers_app, name="customers", rich_help_panel="Your data")

goals_app = entity_app("goals")
goals_app.command(name="list", help="List goals, nearest deadline first.")(
    goals_listing.list_command
)
goals_app.command(name="show", help="Show a goal.")(goals.show_command)
goals_app.command(name="create", help="Create a goal.")(goals.create_command)
goals_app.command(name="edit", help="Edit a goal.")(goals.edit_command)
app.add_typer(goals_app, name="goals", rich_help_panel="Your data")

app.command(
    name="doctor",
    help="Check that the database is up to date and healthy.",
    rich_help_panel="Other",
)(doctor_command)

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
#     dev_app,
#     name="dev",
#     help="Utils for trak developers.",
#     rich_help_panel="Other",
# )
