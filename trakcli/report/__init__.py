import typer

from .commands.project import report_project

app = typer.Typer()


app.command("project")(report_project)
