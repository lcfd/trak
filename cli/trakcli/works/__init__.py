import typer

from trakcli.works.commands.delete import delete_work
from trakcli.works.commands.list import list_works

app = typer.Typer()


app.command("list")(list_works)
app.command("delete")(delete_work)
