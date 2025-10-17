import typer

from trak.edit.project import edit_project
from trak.edit.work import edit_work

# from trak.edit.session import edit_session

app = typer.Typer()


# app.command("session", help="edit a session.")(edit_session)
app.command("work", help="Edit a work.")(edit_work)
app.command("project", help="Edit a project.")(edit_project)
