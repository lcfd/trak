from rich import print
from rich.panel import Panel

from trakcli.utils.base_messages import print_error, print_with_padding


def print_error_no_projects():
    print_error(
        title="You don't have available projects",
        text=(
            "You need run the `trak create project <project name>` "
            "command to create a new project."
        ),
    )

    return

def print_error_work_field(work_id: str, project_id:str, field:str):
    print_error(
        title="Error",
        text=f"Error in {work_id}'s {field} of {project_id} project."
    )

    return

def print_missing_project(projects_in_config):
    renderable_projects_list = "\n • ".join(projects_in_config)
    print_error(
        title="This project doesn't exist",
        text=(
            f"Available projects are: \n\n • {renderable_projects_list}\n\n\n\n"
            'Run the "trak create project <project name>" '
            "command to create a new project."
        ),
    )

    return


def print_project_archived_toggle(project_id: str, archived: bool):
    print("")
    if archived:
        print(
            Panel.fit(
                title=f"[green] The project {project_id} has been archived",
                renderable=print_with_padding(
                    (
                        "From now on this project won't be accessible from lists.\n\n"
                        "[orange3]⭐Tip:[/orange3]\n"
                        "You can run trak [orange3]project "
                        f"archive {project_id}[/orange3] to unarchive it."
                    )
                ),
            )
        )
    else:
        print(
            Panel.fit(
                title=f"[green]󱝢 The project {project_id} has been unarchived",
                renderable=print_with_padding(
                    (
                        "From now on this project will be accessible from lists.\n\n"
                        "[orange3]⭐Tip:[/orange3]\n"
                        f"You can run trak [orange3]project archive "
                        f"{project_id}[/orange3] to archive it."
                    )
                ),
            )
        )


def print_project_broken_configuration(project_id: str):
    print("")
    print(
        Panel.fit(
            title=f"[red]The project {project_id} has broken configuration",
            renderable=print_with_padding(
                ("Please, check the details.json file in your project folder.")
            ),
        )
    )
