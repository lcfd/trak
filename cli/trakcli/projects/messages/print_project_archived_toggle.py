from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_project_archived_toggle(project_id: str, archived: bool):
    rprint("")
    if archived:
        rprint(
            Panel.fit(
                title=f"[green] The project {project_id} has been archived",
                renderable=print_with_padding(
                    (
                        "From now on this project won't be accessible from lists.\n\n"
                        "[orange3]⭐Tip:[/orange3]\n"
                        f"You can run trak [orange3]project archive {project_id}[/orange3] to unarchive it."
                    )
                ),
            )
        )
    else:
        rprint(
            Panel.fit(
                title=f"[green]󱝢 The project {project_id} has been unarchived",
                renderable=print_with_padding(
                    (
                        "From now on this project will be accessible from lists.\n\n"
                        "[orange3]⭐Tip:[/orange3]\n"
                        f"You can run trak [orange3]project archive {project_id}[/orange3] to archive it."
                    )
                ),
            )
        )
