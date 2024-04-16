from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_missing_duration():
    rprint("")
    rprint(
        Panel.fit(
            title="[red]Missing duration[/red]",
            renderable=print_with_padding(
                "You need to provide the duration of the session, in hours or/and minutes (--minutes or/and --hours)."
            ),
        )
    )

    return
