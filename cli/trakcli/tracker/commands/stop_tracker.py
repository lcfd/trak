from datetime import datetime
from rich import print as rprint
from rich.panel import Panel

from trakcli.database.database import stop_trak_session, tracking_already_started
from trakcli.database.models import Record
from trakcli.utils.print_with_padding import print_with_padding


def stop_tracker():
    """
    Stop the current session.
    This will add and end datetime in the end field.
    """

    record = tracking_already_started()

    rprint("")
    if isinstance(record, Record):
        stopped_record = stop_trak_session()

        if stopped_record:
            start_datetime = datetime.fromisoformat(stopped_record.start)
            end_datetime = datetime.fromisoformat(stopped_record.end)
            diff = end_datetime - start_datetime

            all_minutes, _ = divmod(diff.seconds, 60)
            h, m = divmod(all_minutes, 60)

            rprint(
                Panel.fit(
                    title="[bold green]⏹️ Stop[/bold green]",
                    renderable=print_with_padding(
                        (
                            f"The [bold green]{stopped_record.project}[/bold green] session is over.\n\n"
                            f"This session lasted [bold green]{h}h {m}m[/bold green].\n\n"
                            "Good job!"
                        )
                    ),
                )
            )
        else:
            rprint(
                Panel.fit(
                    title="🚨 [red]Error[/red]",
                    renderable=print_with_padding(
                        ("Check your database, there must be something wrong in it.")
                    ),
                )
            )
    else:
        rprint(
            Panel.fit(
                title="💬 No active sessions",
                renderable=print_with_padding(
                    (
                        "There aren't active sessions.\n\n"
                        "Use the command: trak start <project name> to start a new session of work."
                    )
                ),
            )
        )
