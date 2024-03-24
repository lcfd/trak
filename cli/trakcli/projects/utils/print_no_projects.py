from rich import print as rprint
from rich.panel import Panel
from trakcli.utils.print_with_padding import print_with_padding


def print_no_projects():
    rprint("")
    rprint(
        Panel.fit(
            title="[red]You don't have available projects[/red]",
            renderable=print_with_padding(
                "You need run the `trak create project <project name>` command to create a new project."
            ),
        )
    )

    return
