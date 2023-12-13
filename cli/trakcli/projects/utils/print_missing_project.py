from rich import print as rprint
from rich.panel import Panel
from trakcli.utils.print_with_padding import print_with_padding


def print_missing_project(projects_in_config):
    renderable_projects_list = "\n • ".join(projects_in_config)
    rprint("")
    rprint(
        Panel.fit(
            title="[red]Missing project[/red]",
            renderable=print_with_padding(
                "This project doesn't exists.\n\n"
                f"Awailable projects: \n\n • {renderable_projects_list}\n\n\n\n"
                "Try to run the `trak create project <project name>` command if you want to create a new project."
            ),
        )
    )

    return
