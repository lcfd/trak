from rich_toolkit.menu import Option

from trak._OLD.database import get_project_works
from trak.utils.rich_toolkit import create_rich_toolkit_app
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

    rt_app = create_rich_toolkit_app()

    if not isinstance(work_id, int):
        options: list[Option] = [
            {"name": f"({i}) {w.name}", "value": i} for i, w in enumerate(works)
        ]

        try:
            work_id = rt_app.ask(
                title="Work",
                options=options,
                allow_filtering=True,
            )

            if isinstance(work_id, str):
                work_id = int(work_id)

            if work_id is None:
                return None
        except Exception:
            return None

    return work_id, works[work_id].name


def work_properties_picker() -> str:
    """Returns a Project class property selected by the user."""

    work_propeties_options: list[Option] = [
        {"name": property.capitalize(), "value": property}
        for property in Work.__dict__.keys()
        if not (property.startswith("__") and property.endswith("__"))
        and not property.startswith("_")
    ]

    rt_app = create_rich_toolkit_app()
    property = rt_app.ask(
        title="Property", options=work_propeties_options, allow_filtering=True
    )

    return property
