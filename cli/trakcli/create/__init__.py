import typer

from trakcli.create.commands.session import create_session
from trakcli.create.commands.work import create_work
from trakcli.create.commands.project import create_project


app = typer.Typer()


app.command("session")(create_session)
app.command("work")(create_work)
app.command("project")(create_project)
