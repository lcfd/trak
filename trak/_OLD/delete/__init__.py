import typer

from trak.delete.project import delete_project
from trak.delete.session import delete_session
from trak.delete.work import delete_work

app = typer.Typer()


app.command("session", help="Delete a session.")(delete_session)
app.command("work", help="Delete a work.")(delete_work)
app.command("project", help="Delete a project.")(delete_project)
