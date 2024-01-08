import typer

from trakcli.works.commands.delete import delete_work
from trakcli.works.commands.done import done_work
from trakcli.works.commands.list import list_works
from trakcli.works.commands.paid import paid_work

app = typer.Typer()


app.command("list")(list_works)
app.command("delete")(delete_work)
app.command("done")(done_work)
app.command("paid")(paid_work)
