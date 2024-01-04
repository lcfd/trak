import typer

from .commands.main import project

app = typer.Typer()


app.command("a")(project)
