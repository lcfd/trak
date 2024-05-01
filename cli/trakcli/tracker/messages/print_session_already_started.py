from datetime import datetime

from trakcli.database.models import Record
from trakcli.utils.messages.print_info import print_info


def print_session_already_started(record: Record):
    """Notify the user that a session is already ongoing."""

    start_datetime = datetime.fromisoformat(record.start)
    now = datetime.now()
    diff = now - start_datetime

    m, _ = divmod(diff.seconds, 60)
    h, m = divmod(m, 60)

    formatted_start_time = start_datetime.strftime("%Y-%m-%d, %H:%M")

    msg = (
        f"Tracking on [bold green]{record.project}[/bold green] "
        f"already started at {formatted_start_time}.\n\n"
        f"It's been going for [bold green]{h}h {m}m[/bold green]."
    )

    print_info(title="Session already started", text=msg)

    return
