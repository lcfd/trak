import typer

from trakcli.projects.commands.archive import command_project_archive
from trakcli.projects.commands.delete import command_project_delete
from trakcli.projects.commands.list import command_project_list

app = typer.Typer()


app.command(name="list", help="List your projects.")(command_project_list)
app.command(name="delete", help="Delete a project.")(command_project_delete)
app.command(name="archive", help="Archive a project.")(command_project_archive)
