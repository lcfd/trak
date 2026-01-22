import typer

from trak.create.project import create_project
from trak.create.session import create_session
from trak.create.work import create_work

app = typer.Typer()

app.command("session")(create_session)
app.command("work", help="Create a work.")(create_work)
app.command("project", help="Create a new project.")(create_project)
