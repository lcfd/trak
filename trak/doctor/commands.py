import json
import pathlib
from json import JSONDecodeError

from trak.config import get_config, get_db_file_path
from trak.database import get_db_content
from trak.models import Config
from trak.paths import CONFIG_FILE_PATH, DB_FILE_PATH, PROJECTS_FOLDER_PATH
from trak.utils.base_messages import print_error, print_success
from trak.works.models import Work


def doctor_config():
    """Check if the config is in shape."""

    something_wrong = False

    # Does it exists?
    if not CONFIG_FILE_PATH.is_file():
        print_error(
            title="You don't have the config file",
            text="There is something wrong with the initialization.",
        )
        something_wrong = True

    config = get_config()

    try:
        if isinstance(config, dict):
            Config(**config)
    except Exception:
        print_error(
            title="Wrong config file content",
            text=f"Check it out manually at {CONFIG_FILE_PATH}",
        )
        something_wrong = True

    if not something_wrong:
        print_success(
            title="Your configuration is in shape",
            text=f"You can also check it out manually at {CONFIG_FILE_PATH}",
        )


def doctor_sessions():
    something_wrong = False

    db_file_path = get_db_file_path()

    # Does it exists?
    if not db_file_path:
        print_error(
            title="You don't have the db file",
            text=f"Create the file {DB_FILE_PATH}",
        )
        something_wrong = True

    db_content = get_db_content()
    if not db_content:
        print_error(
            title="Broken data in db file",
            text=f"Check the file {DB_FILE_PATH}",
        )
        something_wrong = True

    if not something_wrong:
        print_success(
            title="Your database is in shape",
            text=f"You can also check it out manually at {DB_FILE_PATH}",
        )


def doctor_works():
    something_wrong = False

    projects_path = pathlib.Path(PROJECTS_FOLDER_PATH)

    for x in projects_path.iterdir():
        if not x.is_dir():
            continue

        works_in_project_path = x / "works.json"
        with open(works_in_project_path, "r") as f:
            try:
                works_from_json = json.load(f)
                list(map(lambda w: Work(**w), works_from_json))
            except TypeError as e:
                keyword_error_marker = (
                    "Work.__new__() got an unexpected keyword argument"
                )
                if keyword_error_marker in str(e):
                    print_error(
                        title=f"Wrong fields in {x}",
                        text=f"Wrong field: {str(e).split(" unexpected keyword argument ")[1]}.",
                    )
                something_wrong = True
                continue
            except JSONDecodeError:
                print_error(
                    title=f"Wrong work in {x}",
                    text="There is one or more works that aren't in Json format.",
                )
                continue
            except Exception:
                print_error(
                    title="Something wrong",
                    text='Create an issue on GitHub! \n Use the "trak -i" command the get the link.',
                )
                continue

    if not something_wrong:
        print_success(
            title="Your works are shape",
            text=f"You can also check them out manually at {PROJECTS_FOLDER_PATH}",
        )
