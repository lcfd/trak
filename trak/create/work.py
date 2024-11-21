from datetime import datetime

import questionary

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
    # Required
    project_id: ProjectIdOption = None,
    name: NameOption = None,
    time: TimeOption = None,
    from_datetime: FromDateOption = None,
    to_datetime: ToDateOption = None,
    # Optional
    description: DescriptionOption = "",
    rate: RateOption = 1,
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

    if isinstance(name, str):
        new_work_name = name
    else:
        try:
            new_work_name = str(questionary.text("Name?").ask())
        except Exception:
            print_error(text="Invalid value inserted.")
            return

    new_work_time = None
    if isinstance(time, int):
        new_work_time = time
    else:
        while not isinstance(new_work_time, int):
            question_answer = questionary.text("Hours in budget (>0)?").ask()
            try:
                new_work_time = int(question_answer)
            except Exception:
                print_error(text="Invalid value inserted, it should be a number.")

    new_work_from_datetime = None
    if isinstance(from_datetime, datetime):
        new_work_from_datetime = from_datetime
    else:
        while not isinstance(new_work_from_datetime, datetime):
            question_answer = questionary.text(
                "From when (eg: 2024-12-12T09:00)?"
            ).ask()
            try:
                new_work_from_datetime = datetime.strptime(
                    question_answer, "%Y-%m-%dT%H:%M"
                )
            except Exception:
                print_error(
                    text="Invalid value inserted, it should be valid date time of %Y-%m-%dT%H:%M format."
                )

    new_work_to_datetime = None
    if isinstance(to_datetime, datetime):
        new_work_to_datetime = to_datetime
    else:
        while not isinstance(new_work_to_datetime, datetime):
            question_answer = questionary.text("To when (eg: 2025-01-22T18:00)?").ask()
            try:
                new_work_to_datetime = datetime.strptime(
                    question_answer, "%Y-%m-%dT%H:%M"
                )
            except Exception:
                print_error(
                    text="Invalid value inserted, it should be valid date time of %Y-%m-%dT%H:%M format."
                )
    #
    # Create

    new_work = Work(
        name=new_work_name,
        time=new_work_time,
        from_date=datetime_to_string(new_work_from_datetime),
        to_date=datetime_to_string(new_work_to_datetime),
        rate=rate,
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
