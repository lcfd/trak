import typer

from trak.doctor.commands import doctor_config, doctor_sessions, doctor_works

app = typer.Typer()


app.command("config", help="Check if the config is ok.")(doctor_config)
app.command("sessions", help="Check if the sessions are ok.")(doctor_sessions)
app.command("works", help="Check if the works are ok.")(doctor_works)
