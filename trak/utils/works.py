import questionary
from questionary import Choice

from trak.database import get_project_works
from trak.utils.questionary import questionary_style_select
from trak.works.models import Work


def change_work_field(work: Work, parameter: str, value):
    tpl_dict = work._asdict()
    tpl_dict[parameter] = value
    return Work(**tpl_dict)


def works_picker(
    project_id: str,
    work_id: int | None = None,
) -> tuple[int, str] | None:
    """Check if the provided project_id is in config."""

    works = get_project_works(project_id=project_id)
    if not works:
        return

    if not isinstance(work_id, int):
        work_id = questionary.select(
            "Select the work to delete:",
            choices=[
                Choice(title=f"({i}) {w.name}", value=i) for i, w in enumerate(works)
            ],
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

    return work_id, works[work_id].name
