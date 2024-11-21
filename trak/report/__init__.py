import typer

from trak.report.commands.project import report_project
from trak.report.commands.sessions import report_sessions
from trak.report.commands.works import report_works

app = typer.Typer()


app.command("project")(report_project)
app.command("sessions")(report_sessions)
app.command("works")(report_works)
