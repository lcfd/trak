import typer

from trak.delete.session import delete_session

# from trak.delete.work import delete_work
from trak.delete.project import delete_project


app = typer.Typer()


app.command("session", help="Delete a new session")(delete_session)
# app.command("work", help="Delete a new work")(delete_work)
app.command("project", help="Delete a new project")(delete_project)
