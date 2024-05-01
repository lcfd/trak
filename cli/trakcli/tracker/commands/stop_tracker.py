from datetime import datetime

from trakcli.database.database import stop_trak_session, tracking_already_started
from trakcli.database.models import Record
from trakcli.utils.messages.print_error import print_error
from trakcli.utils.messages.print_info import print_info
from trakcli.utils.messages.print_success import print_success


def stop_tracker():
    """
    Stop the current session.
    This will add and end datetime in the end field.
    """

    record = tracking_already_started()

    if isinstance(record, Record):
        stopped_record = stop_trak_session()

        if stopped_record:
            start_datetime = datetime.fromisoformat(stopped_record.start)
            end_datetime = datetime.fromisoformat(stopped_record.end)
            diff = end_datetime - start_datetime

            all_minutes, _ = divmod(diff.seconds, 60)
            h, m = divmod(all_minutes, 60)

            print_success(
                title="⏹️ Stop",
                text=(
                    f"The [bold green]{stopped_record.project}[/bold green] session is over.\n\n"
                    f"This session lasted [bold green]{h}h {m}m[/bold green].\n\n"
                    "Good job!"
                ),
            )
        else:
            print_error(
                title="Project not provided",
                text=(
                    "There are multiple sessions running.\n\n"
                    "You need to pick a project from the list."
                ),
            )
    else:
        print_info(
            title="No active sessions",
            text=(
                "There aren't active sessions to stop.\n\n"
                'Use the command "trak start" to start a new session of work.'
            ),
        )
