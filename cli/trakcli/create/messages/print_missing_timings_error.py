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
                "You different options: \n"
                "• Use the --today or --date flags as starting moment in combination with --minutes / --hours flags to add to the starting moment.\n"
                "• Use just --minutes / --hours flags to subract from now.\n"
                "• Use the --start and --end flags.\n\n"
                "[yellow1]⭐Tip[/yellow1]: All flags come with short versions. \n"
                '       For example, "--minutes" can be written as "-m".\n'
                "       You can see them using --help."
            ),
        )
    )

    return
