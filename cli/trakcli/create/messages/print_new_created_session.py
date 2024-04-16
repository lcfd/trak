from rich import print as rprint
from rich.panel import Panel

from trakcli.database.models import Record
from trakcli.utils.print_with_padding import print_with_padding


def print_new_created_session(project_id: str, new_session: Record):
    start, _, _ = new_session.start.replace("T", " ").partition(".")
    end, _, _ = new_session.end.replace("T", " ").partition(".")
    billable = "Yes" if new_session.billable else "No"

    rprint("")
    rprint(
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
