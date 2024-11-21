import typer

from trak.create.work import create_work

# from trak.create.commands.session import create_session
from trak.create.project import create_project


app = typer.Typer()


# app.command("session", help="Create a new session.")(create_session)
app.command("work", help="Create a work.")(create_work)
app.command("project", help="Create a new project.")(create_project)
