from trakcli.utils.messages.print_error import print_error


def print_missing_project(projects_in_config):
    renderable_projects_list = "\n • ".join(projects_in_config)
    print_error(
        title="This project doesn't exist",
        text=(
            f"Available projects are: \n\n • {renderable_projects_list}\n\n\n\n"
            'Run the "trak create project <project name>" command to create a new project.'
        ),
    )

    return
