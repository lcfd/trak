from typing import Annotated

import typer

from trakcli.create.annotations import (
    DescriptionOption,
    FromDateOption,
    NameOption,
    ProjectIdOption,
    RateOption,
    TimeOption,
    ToDateOption,
)
from trakcli.report.annotations import ArchivedOption
from trakcli.utils.dates import datetime_to_string
from trakcli.utils.base_messages import print_error, print_success, print_warning
from trakcli.utils.projects import db_get_project_details, projects_picker
from trakcli.works.database import (
    get_project_works_from_config_folder,
    set_project_works_in_config_folder,
)
from trakcli.works.models import Work


def create_work(
    work_id: Annotated[
        str,
        typer.Argument(help="The id for the new work."),
    ],
    name: NameOption,
    time: TimeOption,
    from_date: FromDateOption,
    to_date: ToDateOption,
    description: DescriptionOption = "",
    rate: RateOption = 1,
    project_id: ProjectIdOption = None,
    archived: ArchivedOption = False,
):
    project_id = projects_picker(project_id=project_id, archived=archived)

    if not project_id:
        return

    # if project_id in projects_in_config:
    details = db_get_project_details(project_id)

    # Check if project esists
    if details:
        works = get_project_works_from_config_folder(project_id)

        # Check if id already exists
        if works is not None:
            work_ids = [w.id for w in works]
            if work_id in work_ids:
                print_warning(
                    title="This work already exists",
                    text=(
                        f'The id "{work_id}" has already been used in the '
                        f'"{project_id}" project.\n\n'
                        f'You can check ALL the works in the project "{project_id}" '
                        "by using the command:\n"
                        f"trak works list {project_id} --done\n\n"
                        "Use a different value for work_id."
                    ),
                )

                return

        new_work = Work(
            id=work_id,
            name=name,
            time=time,
            rate=rate,
            from_date=datetime_to_string(from_date),
            to_date=datetime_to_string(to_date),
            description=description,
            done=False,
            paid=False,
        )

        if works is not None:
            works.append(new_work)
        else:
            works = [new_work]

        set_project_works_in_config_folder(project_id, works)

        print_success(
            title="Work created",
            text=f"Work [green]{work_id}[/green] created.",
        )

        return
    else:
        print_error(
            title="Error in config",
            text="Error in details file in project's configuration.",
        )

        return
