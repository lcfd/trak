import typer

from trakcli.works.commands.list import list_works


app = typer.Typer()


app.command("list")(list_works)
