from datetime import datetime
from typing import Optional

import typer
from rich import print as rprint
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from typing_extensions import Annotated

from trakcli import __app_name__, __version__, __website__
from trakcli.config.commands import app as config_app
from trakcli.config.main import CONFIG_FILE_PATH
from trakcli.database.basic import get_json_file_content
from trakcli.database.database import (
    add_track_field,
    get_current_session,
    get_record_collection,
    stop_track_field,
    tracking_already_started,
)
from trakcli.database.models import Record
from trakcli.dev.commands import app as dev_app
from trakcli.initialize import initialize_trak
from trakcli.utils.print_with_padding import print_with_padding

console = Console()

app = typer.Typer()

# Initialize trak required files and settings
initialize_trak()

app.add_typer(dev_app, name="dev")
app.add_typer(config_app, name="config")

# Read the config at CONFIG_FILE_PATH
config = get_json_file_content(CONFIG_FILE_PATH)


def _version_callback(value: bool) -> None:
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


def _website_callback(value: bool) -> None:
    """
    Launch the usetrak.com website.
    """
    if value:
        typer.launch(__website__)

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
    website: Optional[bool] = typer.Option(
        None,
        "--website",
        "-w",
        help="Launch the usetrak.com website.",
        callback=_website_callback,
        is_eager=True,
    ),
) -> None:
    return


@app.command(name="start", short_help="Start trak")
def start_tracker(
    project: str,
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="The tracked time is billable. Useful in the reporting phase.",
            show_default=True,
        ),
    ] = False,
    category: Annotated[
        str,
        typer.Option(
            "--category",
            "-c",
            help="Add a category to the tracked time. Useful in the reporting phase.",
        ),
    ] = "",
    tag: Annotated[
        str,
        typer.Option(
            "--tag",
            "-t",
            help="Add a tag to the tracked time. Useful in the reporting phase.",
        ),
    ] = "",
):
    """
    Start tracking a project by name.
    """

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
        rprint(
            Panel.fit(
                title="▶️  Start",
                renderable=print_with_padding(
                    f"""[bold green]{project}[/bold green] started.

Have a good session!"""
                ),
            )
        )
    else:
        rprint(
            Panel.fit(
                title="💬 Already started",
                renderable=print_with_padding(
                    f"""
Tracking on [bold green]{project}[/bold green] already started \
at {datetime.fromisoformat(record['start']).strftime("%m/%d/%Y, %H:%M")}"""
                ),
            )
        )


@app.command("stop", short_help="Stop trak")
def stop_tracker():
    """
    Stop tracking the current project.
    """

    record = tracking_already_started()
    if record:
        stop_track_field()
        message = print_with_padding(
            f"""
The [bold green]{record['project']}[/bold green] session is over. 

Good job!"""
        )

        rprint(Panel.fit(title="⏹️  Stop", renderable=message))
    else:
        rprint(
            Panel.fit(
                title="💬 No active sessions",
                renderable=print_with_padding(
                    """Ther aren't active sessions. 

Use the command: trak start <project name> to start a new session of work."""
                ),
            )
        )


@app.command()
def status(
    starship: Annotated[
        bool,
        typer.Option(
            "--starship",
            "-s",
            help="Show the output formatted for Starship.",
        ),
    ] = False,
):
    """
    Show the status of the current session.
    """

    current_session = get_current_session()

    if current_session:
        start_datetime = datetime.fromisoformat(current_session["start"])
        formatted_start_datetime = start_datetime.strftime("%Y-%m-%d, %H:%M")

        now = datetime.now()
        diff = now - start_datetime

        m, _ = divmod(diff.seconds, 60)
        h, m = divmod(m, 60)

        if starship:
            print(
                f"""⏰ {'( DEV MODE) ' if config['development'] else ''}\
{current_session['project']} ⌛ {h}h {m}m"""
            )
        else:
            rprint(
                Panel(
                    title="💬 Current status",
                    renderable=print_with_padding(
                        f"""{'( DEV MODE) ' if config['development'] else ''}
Project: [bold]{current_session['project']}[/bold]
Started: {formatted_start_datetime}
Time: [bold]{h}h {m}m[/bold]""",
                    ),
                )
            )
    else:
        if starship:
            print(
                f"⏰ {'( DEV MODE) ' if config['development'] else ''}\
No active session"
            )
        else:
            rprint(
                Panel(
                    title="💬 No active session",
                    renderable=print_with_padding(
                        """Ther aren't active sessions. 

Use the command: trak start <project name> to start a new session of work."""
                    ),
                )
            )


@app.command()
def report(
    project: str,
    when: Annotated[
        str,
        typer.Option(
            "--when",
            "-w",
            help="Look for records in a specific date or range by keyword. \
Values may be: \
- today \
- yesterday \
- month: the current month \
- yyyy-mm-dd: like 2023-10-08",
        ),
    ] = "",
    category: Annotated[str, typer.Option("--category", "-c")] = "",
    tag: Annotated[str, typer.Option("--tag", "-t")] = "",
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
):
    """
    Report stats for projects.
    """

    get_record_collection(
        project=project, billable=billable, category=category, tag=tag, when=when
    )
