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

    if isinstance(record, Record):
        stop_trak_session()
        rprint(
            Panel.fit(
                title="⏹️  Stop",
                renderable=print_with_padding(
                    (
                        f"The [bold green]{record.project}[/bold green] session is over.\n\n"
                        "Good job!"
                    )
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
