from rich import print

from trak.models import Record
from trak.utils.base_messages import print_error, print_success


def print_error_no_projects():
    print_error(
        title="You don't have available projects",
        text=(
            "You need run the `trak create project <project name>` "
            "command to create a new project."
        ),
    )

    return


def print_error_work_field(work_id: str, project_id: str, field: str):
    print_error(
        title="Error", text=f"Error in {work_id}'s {field} of {project_id} project."
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
        print_success(
            title=f"[green] The project {project_id} has been archived",
            text=(
                "From now on this project won't be accessible from lists.\n\n"
                "[orange3]⭐Tip:[/orange3]\n"
                "You can run trak [orange3]project "
                f"archive {project_id}[/orange3] to unarchive it."
            ),
        )
    else:
        print_success(
            title=f"[green]󱝢 The project {project_id} has been unarchived",
            text=(
                "From now on this project will be accessible from lists.\n\n"
                "[orange3]⭐Tip:[/orange3]\n"
                f"You can run trak [orange3]project archive "
                f"{project_id}[/orange3] to archive it."
            ),
        )


def print_project_broken_configuration(project_id: str):
    print("")
    print_error(
        title=f"The project {project_id} has broken configuration",
        text="Please, check the details.json file in your project folder.",
    )


def print_missing_duration():
    print("")
    print_error(
        title="Missing duration",
        text=(
            "You need to provide the duration of the session, "
            "in hours or/and minutes (--minutes or/and --hours)."
        ),
    )


def print_missing_timings_error():
    print("")
    print_error(
        title="Missing timings",
        text=(
            "You need to provide the timings for your session. \n"
            "There are some options:\n"
            "• Use the --date flags as starting moment in combination "
            "with --minutes and/or --hours to add to --date.\n"
            "• Use just --minutes and/or --hours flags to subract from now.\n"
            "• Use the --start and --end flags."
        ),
    )


def print_new_created_session(project_id: str, new_session: Record):
    start, _, _ = new_session.start.replace("T", " ").partition(".")
    end, _, _ = new_session.end.replace("T", " ").partition(".")
    billable = "Yes" if new_session.billable else "No"

    print("")
    print_success(
        title=f"New session created for project {project_id}",
        text=(
            f"[yellow1]Timings[/yellow1]\n"
            f"start: {start}\n"
            f"end: {end}\n\n"
            f"[yellow1]Properties[/yellow1]\n"
            f"billable: {billable}\n"
            f"category: {new_session.category or 'No category'}\n"
            f"tag: {new_session.tag or 'No tag'}"
        ),
    )
