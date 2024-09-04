from trakcli.utils.messages import print_error


def print_error_no_projects():
    print_error(
        title="You don't have available projects",
        text=(
            "You need run the `trak create project <project name>` command to create a new project."
        ),
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
