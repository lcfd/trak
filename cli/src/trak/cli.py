from datetime import datetime
from typing import Optional
import typer
from rich import print
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from trak import __app_name__, __version__
from trak.database import (
    Record,
    add_track_field,
    check_if_database_exists,
    stop_track_field,
    tracking_already_started,
)

console = Console()

app = typer.Typer()


def _version_callback(value: bool) -> None:
    if value:
        print(
            Panel(
                renderable=Align.center(f"{__app_name__} v{__version__}"),
                title=__app_name__,
                padding=(2),
            ),
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    return


@app.command()
def start(project: str, billable: bool = False, tag: str = "", category: str = ""):
    """Start tracking a project."""

    if not check_if_database_exists():
        print(Panel.fit("🚨 You don't have a database"))
        return

    if not project:
        project = typer.prompt("Which project do you want to track?")

    record = tracking_already_started()

    if not record:
        add_track_field(
            Record(
                project=project,
                start=datetime.now().isoformat(),
                billable=billable,
                category=category,
                tag=tag,
            )
        )
        print(
            Panel.fit(
                title="▶️  Start",
                renderable=f"[bold green]{project}[/bold green] started. Have a good session!",
            )
        )
    else:
        print(
            Panel.fit(
                title="💬 Already started",
                renderable=f"Tracking on [bold green]{project}[/bold green] already started at {record['start']}",
            )
        )


@app.command()
def stop():
    """Stop tracking a project."""

    if not check_if_database_exists():
        print(Panel.fit("🚨 You don't have a database"))
        return

    record = tracking_already_started()
    if record:
        stop_track_field()

        print(
            Panel.fit(
                title="⏹️  Stop",
                renderable=f"The [bold green]{record['project']}[/bold green] session is over. Good job!",
            )
        )
    else:
        print(
            Panel.fit(
                title="💬 No active sessions",
                renderable="There are no active sessions. Use the command: trak start <project name>.",
            )
        )


@app.command()
def report(project: str, when: str = typer.Option(default="month")):
    """Report stats for projects."""

    print(Panel.fit(f"Report project {project} — {when}"))
