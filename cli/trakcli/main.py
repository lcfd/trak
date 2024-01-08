from datetime import datetime
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from typing_extensions import Annotated

from trakcli.callbacks import (
    issues_callback,
    report_bug_callback,
    repository_callback,
    version_callback,
    website_callback,
)
from trakcli.config.commands import app as config_app
from trakcli.config.main import get_config
from trakcli.create import app as create_app
from trakcli.database.database import (
    add_session,
    get_current_session,
    stop_trak_session,
    tracking_already_started,
)
from trakcli.database.models import Record
from trakcli.dev.commands import app as dev_app
from trakcli.initialize import initialize_trak
from trakcli.projects.commands import app as projects_app
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.report import app as report_app
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.works import app as works_app

console = Console()

app = typer.Typer()

# Initialize trak required files and settings
initialize_trak()


# Add subcommands
app.add_typer(
    dev_app, name="dev", help="Utils for developers who wants to work on trak."
)
app.add_typer(config_app, name="config", help="Interact with your configuration.")
app.add_typer(projects_app, name="projects", help="Interact with your projects.")
app.add_typer(create_app, name="create", help="Create something in trak.")
app.add_typer(works_app, name="works", help="Interact with your works.")
app.add_typer(report_app, name="report", help="Get useful insights from your records.")

# app.command()(report)


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version.",
        callback=version_callback,
        is_eager=True,
    ),
    website: Optional[bool] = typer.Option(
        None,
        "--website",
        "-w",
        help="Launch the usetrak.com website.",
        callback=website_callback,
        is_eager=True,
    ),
    repository: Optional[bool] = typer.Option(
        None,
        "--repository",
        "-r",
        help="Launch the trak repository.",
        callback=repository_callback,
        is_eager=True,
    ),
    issues: Optional[bool] = typer.Option(
        None,
        "--issues",
        "-i",
        help="Launch the trak issues page on Github.",
        callback=issues_callback,
        is_eager=True,
    ),
    bug: Optional[bool] = typer.Option(
        None,
        "--bug",
        "-b",
        help="Report a bug on Github.",
        callback=report_bug_callback,
        is_eager=True,
    ),
) -> None:
    return


@app.command(name="start", help="Start a trak session.")
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
    projects_in_config = get_projects_from_config()

    if not record:
        if project in projects_in_config:
            add_session(
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
                        (
                            f"[bold green]{project}[/bold green] started.\n\n"
                            "Have a good session!"
                        )
                    ),
                )
            )
        else:
            print_missing_project(projects_in_config)

            return
    else:
        formatted_start_time = datetime.fromisoformat(record["start"]).strftime(
            "%m/%d/%Y, %H:%M"
        )
        msg = (
            f"Tracking on [bold green]{record['project']}[/bold green] "
            f"already started at {formatted_start_time}"
        )
        rprint(
            Panel.fit(
                title="💬 Already started",
                renderable=print_with_padding(msg),
            )
        )

    return


@app.command("stop", help="Stop the current trak session.")
def stop_tracker():
    """
    Stop tracking the current project.
    """

    record = tracking_already_started()
    if record:
        stop_trak_session()
        message = print_with_padding(
            (
                f"The [bold green]{record['project']}[/bold green] session is over.\n\n"
                "Good job!"
            )
        )

        rprint(Panel.fit(title="⏹️  Stop", renderable=message))
    else:
        rprint(
            Panel.fit(
                title="💬 No active sessions",
                renderable=print_with_padding(
                    """There aren't active sessions.

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

    CONFIG = get_config()

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
                f"""⏰ {'( DEV MODE) ' if CONFIG['development'] else ''}\
{current_session['project']} ⌛ {h}h {m}m"""
            )
        else:
            rprint(
                Panel.fit(
                    title="💬 Current status",
                    renderable=print_with_padding(
                        f"""Project: [bold]{current_session['project']}[/bold]
Started: {formatted_start_datetime}
Time: [bold]{h}h {m}m[/bold]""",
                    ),
                )
            )
    else:
        if starship:
            print(
                f"⏰ {'( DEV MODE) ' if CONFIG['development'] else ''}\
No active session"
            )
        else:
            rprint(
                Panel.fit(
                    title="💬 No active session",
                    renderable=print_with_padding(
                        (
                            "There is no ongoing session at the moment.\n\n"
                            "Use the command: trak start <project name> to start a new session of work."
                        )
                    ),
                )
            )

    return
