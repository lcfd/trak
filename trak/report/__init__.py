import typer

from trak.report.project import report_project
from trak.report.sessions import report_sessions
from trak.report.works import report_works

app = typer.Typer()


app.command("project")(report_project)
app.command("sessions")(report_sessions)
app.command("works")(report_works)
