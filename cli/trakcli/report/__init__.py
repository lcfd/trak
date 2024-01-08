import typer

from .commands.report_project import report_project

app = typer.Typer()


app.command("project")(report_project)
app.command("projects")(report_project)
