from datetime import datetime

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
from trak.forms.fields import datetime_field
from trak.report.annotations import ArchivedOption
from trak.utils.base_messages import print_error, print_success
from trak.utils.dates import datetime_to_string
from trak.utils.projects import project_exists, projects_picker
from trak.utils.rich_toolkit import create_rich_toolkit_app
from trak.works.models import Work


def create_work(
    # Required
    project_id: ProjectIdOption = None,
    name: NameOption = None,
    time: TimeOption = None,
    from_datetime: FromDateOption = None,
    to_datetime: ToDateOption = None,
    # Optional
    description: DescriptionOption = "",
    rate: RateOption = None,
    archived: ArchivedOption = False,
):
    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    project_id = projects_picker(project_id=project_id, archived=archived)
    if not project_id:
        return

    works = get_project_works(project_id)

    #
    # Aks for data

    rt_app = create_rich_toolkit_app()

    if isinstance(name, str):
        new_work_name = name
    else:
        try:
            new_work_name = rt_app.input(title="Readable name?")
        except Exception:
            print_error(text="Invalid value inserted.")
            return

    new_work_time = None
    if isinstance(time, int):
        new_work_time = time
    else:
        while not isinstance(new_work_time, int):
            question_answer = rt_app.input(title="Hours in budget (>0)?")
            try:
                new_work_time = int(question_answer)
            except Exception:
                print_error(text="Invalid value inserted, it should be a number.")

    new_rate = None
    if isinstance(rate, int):
        new_rate = rate
    else:
        while not isinstance(new_rate, int):
            question_answer = rt_app.input(title="Hourly rate?")
            try:
                new_rate = int(question_answer)
            except Exception:
                print_error(text="Invalid value inserted, it should be a number.")

    new_work_from_datetime = datetime_field(
        title="From when (eg: 2024-12-12T09:00)?", value=from_datetime
    )

    new_work_to_datetime = datetime_field(
        title="To when (eg: 2025-01-22T18:00)?", value=from_datetime
    )

    #
    # Create

    new_work = Work(
        name=new_work_name,
        time=new_work_time,
        from_date=datetime_to_string(new_work_from_datetime),
        to_date=datetime_to_string(new_work_to_datetime),
        rate=new_rate,
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
