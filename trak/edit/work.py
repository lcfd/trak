from typing import Annotated, Optional

import typer

from trak.database import get_project_works, save_project_works
from trak.forms.fields import datetime_field
from trak.utils.base_messages import print_error, print_success
from trak.utils.dates import datetime_to_string
from trak.utils.projects import project_exists, projects_picker
from trak.utils.rich_toolkit import create_rich_toolkit_app, get_default_value
from trak.utils.works import work_properties_picker, works_picker
from trak.works.models import WORK_FIELDS_TYPES, Work

ProjectIdOption = Annotated[
    Optional[str],
    typer.Option(
        "--project-id",
        help="The id of the work's project.",
    ),
]

WorkIdOption = Annotated[
    Optional[int],
    typer.Option(
        "--id",
        help="The id of the work you want to delete.",
    ),
]


def edit_work(
    id: WorkIdOption = None,
    project_id: ProjectIdOption = None,
):
    """Edit a work from a project."""

    rt_app = create_rich_toolkit_app()

    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    project_id = projects_picker(project_id=project_id, archived=False)
    if not project_id:
        return

    works_picker_result = works_picker(project_id=project_id, work_id=id)
    if not works_picker_result:
        return

    work_id, work_name = works_picker_result

    works = get_project_works(project_id)
    if not works:
        return

    work_to_edit = works[work_id]._asdict()
    property_to_change = work_properties_picker()

    if WORK_FIELDS_TYPES[property_to_change] == "bool":
        value = rt_app.confirm(title=f"Is it {property}?")
    if WORK_FIELDS_TYPES[property_to_change] == "datetime":
        value = datetime_field(title="Change the current value")
    else:
        value = rt_app.input(
            title="Change the current value",
            default=get_default_value(value=work_to_edit[property_to_change]),
        )

    confirm = rt_app.confirm(title="Do you want to save the changes?")

    if not confirm:
        return

    # Actually edit the property
    work_to_edit[property_to_change] = value

    try:
        updated_work = Work(
            name=work_to_edit["name"],
            time=int(work_to_edit["time"]),
            rate=int(work_to_edit["rate"]),
            from_date=datetime_to_string(work_to_edit["from_date"]),
            to_date=datetime_to_string(work_to_edit["to_date"]),
            description=str(work_to_edit["description"]),
            done=work_to_edit["done"],
            paid=work_to_edit["paid"],
        )
    except Exception:
        print_error(text="Something wrong happened while updating data.")
        return

    works[work_id] = updated_work
    save_project_works(project_id, works)

    print_success(
        title="Success",
        text=f"Work [green]{work_name} (id {work_id})[/green] successfully updated.",
    )
