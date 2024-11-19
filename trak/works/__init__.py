import typer

from trak.works.commands.delete import delete_work
from trak.works.commands.done import done_work
from trak.works.commands.list import list_works
from trak.works.commands.paid import paid_work

app = typer.Typer()


app.command("list")(list_works)
app.command("delete")(delete_work)
app.command("done")(done_work)
app.command("paid")(paid_work)
