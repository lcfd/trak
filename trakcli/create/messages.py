from rich import print
from rich.panel import Panel

from trakcli.models import Record
from trakcli.utils.base_messages import print_with_padding


def print_missing_duration():
    print("")
    print(
        Panel.fit(
            title="[red]Missing duration[/red]",
            renderable=print_with_padding(
                (
                    "You need to provide the duration of the session, "
                    "in hours or/and minutes (--minutes or/and --hours)."
                )
            ),
        )
    )

    return


def print_missing_timings_error():
    print("")
    print(
        Panel.fit(
            title="[red]Missing timings[/red]",
            renderable=print_with_padding(
                "You need to provide the timings for your session. \n"
                "You different options: \n"
                "• Use the --today or --date flags as starting moment in combination "
                "with --minutes / --hours flags to add to the starting moment.\n"
                "• Use just --minutes / --hours flags to subract from now.\n"
                "• Use the --start and --end flags.\n\n"
                "[yellow1]⭐Tip[/yellow1]: All flags come with short versions. \n"
                '       For example, "--minutes" can be written as "-m".\n'
                "       You can see them using --help."
            ),
        )
    )

    return


def print_new_created_session(project_id: str, new_session: Record):
    start, _, _ = new_session.start.replace("T", " ").partition(".")
    end, _, _ = new_session.end.replace("T", " ").partition(".")
    billable = "Yes" if new_session.billable else "No"

    print("")
    print(
        Panel.fit(
            title=f"[green]New session created for project {project_id}",
            renderable=print_with_padding(
                (
                    f"[yellow1]Timings[/yellow1]\n"
                    f"start: {start}\n"
                    f"end: {end}\n\n"
                    f"[yellow1]Properties[/yellow1]\n"
                    f"billable: {billable}\n"
                    f"category: {new_session.category or 'No category'}\n"
                    f"tag: {new_session.tag or 'No tag'}"
                )
            ),
        )
    )
