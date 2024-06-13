import json
import pathlib

from trakcli.config.main import TRAK_FOLDER
from trakcli.works.models import Work


def get_project_works_from_config(project_id: str):
    """Get the project works in the config by id."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

    if project_path.exists() and project_path.is_dir():
        works_path = project_path / "works.json"
        if works_path.exists() and works_path.is_file():
            with open(works_path, "r") as f:
                try:
                    works_from_json = json.load(f)
                    works_list: list[Work] = list(
                        map(lambda w: Work(**w), works_from_json)
                    )
                    return works_list
                except Exception:
                    return None
    else:
        return None


def set_project_works_in_config(project_id: str, works: list[dict]):
    """Get the project works in the config by id."""

    project_path = pathlib.Path(TRAK_FOLDER / "projects" / project_id)

    if project_path.exists() and project_path.is_dir():
        works_path = project_path / "works.json"
        if works_path.exists() and works_path.is_file():
            with open(works_path, "w") as works_file:
                json.dump(works, works_file, indent=2, separators=(",", ": "))
    else:
        return None
