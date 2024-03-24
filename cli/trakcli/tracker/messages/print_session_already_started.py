from datetime import datetime

from rich import print
from rich.panel import Panel

from trakcli.database.models import Record
from trakcli.utils.print_with_padding import print_with_padding


def print_session_already_started(record: Record):
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

    print("")
    print(
        Panel.fit(
            title="💬 Already started",
            renderable=print_with_padding(msg),
        )
    )

    return
