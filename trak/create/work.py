from trak.create.annotations import (
    DescriptionOption,
    FromDateOption,
    NameOption,
    ProjectIdOption,
    RateOption,
    TimeOption,
    ToDateOption,
)
from trak.database import get_project_works, save_project_works
from trak.report.annotations import ArchivedOption
from trak.utils.base_messages import print_error, print_success
from trak.utils.dates import datetime_to_string
from trak.utils.projects import project_exists, projects_picker
from trak.works.models import Work


def create_work(
    name: NameOption,
    time: TimeOption,
    from_date: FromDateOption,
    to_date: ToDateOption,
    description: DescriptionOption = "",
    rate: RateOption = 1,
    project_id: ProjectIdOption = None,
    archived: ArchivedOption = False,
):
    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    project_id = projects_picker(project_id=project_id, archived=archived)
    if not project_id:
        return

    works = get_project_works(project_id)

    new_work = Work(
        name=name,
        time=time,
        rate=rate,
        from_date=datetime_to_string(from_date),
        to_date=datetime_to_string(to_date),
        description=description,
        done=False,
        paid=False,
    )

    if isinstance(works, list):
        works.append(new_work)
    else:
        works = [new_work]

    save_project_works(project_id, works)

    print_success(
        title="Work created",
        text=f"Work [green]{name}[/green] created.",
    )
