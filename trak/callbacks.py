import typer
from rich import print as rprint
from rich.align import Align
from rich.panel import Panel

from trak.__init__ import (
    __app_name__,
    __docs__,
    __git_repository__,
    __version__,
    __website__,
)


def main_version_callback(value: bool) -> None:
    """
    Print the application version.
    """
    if value:
        rprint("")
        rprint(
            Panel.fit(
                renderable=Align.center(f"{__app_name__} v{__version__}"),
                title=__app_name__,
                padding=(2),
            ),
        )
        raise typer.Exit()


def main_website_callback(value: bool) -> None:
    """
    Launch the usetrak.com website.
    """
    if value:
        typer.launch(__website__)
        raise typer.Exit()


def main_repository_callback(value: bool) -> None:
    """
    Launch the usetrak.com website.
    """
    if value:
        typer.launch(__git_repository__)
        raise typer.Exit()


def main_issues_callback(value: bool) -> None:
    """
    Launch issues page.
    """
    if value:
        typer.launch("https://github.com/lcfd/trak/issues")
        raise typer.Exit()


def main_report_bug_callback(value: bool) -> None:
    """
    Launch report bug page.
    """
    if value:
        typer.launch("https://github.com/lcfd/trak/issues/new")
        raise typer.Exit()


def main_docs_callback(value: bool) -> None:
    """
    Launch the docs.usetrak.com website.
    """
    if value:
        typer.launch(__docs__)
        raise typer.Exit()
