from datetime import datetime
from typing import Annotated, Optional

import typer

from trak.database import add_session, get_running_session
from trak.models import Record
from trak.tracker.messages import print_session_already_started
from trak.utils.base_messages import print_success
from trak.utils.projects import projects_picker


def start_tracker(
    project_id: Annotated[
        Optional[str],
        typer.Argument(
            help="The id of the project you want to start tracking.",
        ),
    ] = None,
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
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """
    Start tracking a project by project_id.
    """

    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    record = get_running_session()

    if not isinstance(record, Record):
        add_session(
            Record(
                project=project_id,
                start=datetime.now().isoformat(timespec="seconds"),
                billable=billable,
                category=category,
                tag=tag,
            )
        )
        print_success(
            title="▶️  Start",
            text=(f"[green]{project_id}[/green] started.\n\n" "Have a good session!"),
        )
    else:
        print_session_already_started(record)

    return
