import typer

from trak.projects.commands.archive import command_archive_project
from trak.projects.commands.delete import command_delete_project
from trak.projects.commands.list import command_list_project

app = typer.Typer()

app.command(name="list", help="List your projects.")(command_list_project)
app.command(name="delete", help="Delete a project.")(command_delete_project)
app.command(name="archive", help="Archive a project.")(command_archive_project)
