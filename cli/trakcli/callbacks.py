import typer
from rich import print as rprint
from rich.align import Align
from rich.panel import Panel

from trakcli.__init__ import __app_name__, __git_repository__, __version__, __website__


def version_callback(value: bool) -> None:
    """
    Print the application version.
    """
    if value:
        rprint(
            Panel(
                renderable=Align.center(f"{__app_name__} v{__version__}"),
                title=__app_name__,
                padding=(2),
            ),
        )
        raise typer.Exit()


def website_callback(value: bool) -> None:
    """
    Launch the usetrak.com website.
    """
    if value:
        typer.launch(__website__)
        raise typer.Exit()


def repository_callback(value: bool) -> None:
    """
    Launch the usetrak.com website.
    """
    if value:
        typer.launch(__git_repository__)
        raise typer.Exit()


def issues_callback(value: bool) -> None:
    """
    Launch issues page.
    """
    if value:
        typer.launch("https://github.com/lcfd/trak/issues")
        raise typer.Exit()


def report_bug_callback(value: bool) -> None:
    """
    Launch report bug page.
    """
    if value:
        typer.launch("https://github.com/lcfd/trak/issues/new")
        raise typer.Exit()
