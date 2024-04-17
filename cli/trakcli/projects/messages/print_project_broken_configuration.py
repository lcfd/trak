from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_project_broken_configuration(project_id: str):
    rprint("")
    rprint(
        Panel.fit(
            title=f"[red]The project {project_id} has broken configuration",
            renderable=print_with_padding(
                ("Please, check the details.json file in your project folder.")
            ),
        )
    )
