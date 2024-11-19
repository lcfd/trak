from datetime import datetime

from trak.database import stop_trak_session, tracking_already_started
from trak.models import Record
from trak.utils.base_messages import print_info, print_success, print_error


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
                    f"The [bold green]{stopped_record.project}[/bold green]"
                    " session is over.\n\n"
                    f"This session lasted [bold green]{h}h {m}m[/bold green].\n\n"
                    "Good job!"
                ),
            )
        else:
            print_error(
                title="No session to stop",
                text=("At the moment you don't have any session to stop"),
            )
    else:
        print_info(
            title="No active sessions",
            text=(
                "There aren't active sessions to stop.\n\n"
                'Use the command "trak start" to start a new session of work.'
            ),
        )
