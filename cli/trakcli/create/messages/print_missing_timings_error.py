from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_missing_timings_error():
    rprint("")
    rprint(
        Panel.fit(
            title="[red]Missing timings[/red]",
            renderable=print_with_padding(
                "You need to provide the timings for your session. \n"
                "You can use the --today and --minutes or --hours flags, or the --start and --end flags instead.\n\n"
                'Tip: All flags come with short versions. For example, "--minutes" can be written as "-m".'
            ),
        )
    )

    return
