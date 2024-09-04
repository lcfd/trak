import json
import pathlib

from trakcli.config.main import PROJECTS_FOLDER_PATH
from trakcli.works.models import Work


def get_works_path(project_id: str):
    project_path = pathlib.Path(PROJECTS_FOLDER_PATH / project_id)

    if not project_path.exists() or not project_path.is_dir():
        return None

    return project_path / "works.json"


def get_project_works_from_config_folder(project_id: str):
    """Get the project works in the config by id."""

    works_path = get_works_path(project_id)

    if works_path is not None and works_path.exists() and works_path.is_file():
        with open(works_path, "r") as f:
            try:
                works_from_json = json.load(f)
                works_list: list[Work] = list(map(lambda w: Work(**w), works_from_json))
                return works_list
            except Exception:
                return None


def set_project_works_in_config_folder(project_id: str, works: list[Work]):
    """Get the project works in the config by id."""

    works_path = get_works_path(project_id)

    if works_path is not None and works_path.exists() and works_path.is_file():
        with open(works_path, "w") as works_file:
            json.dump(
                [w._asdict() for w in works],
                works_file,
                indent=2,
                separators=(",", ": "),
            )
