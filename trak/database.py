import json
from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich import padding, print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich_toolkit.menu import Option

from trak.config import get_db_file_path, get_works_path
from trak.models import Record
from trak.utils.base_messages import print_error, print_info, print_with_padding
from trak.utils.dates import format_datetime_readable, same_week
from trak.utils.filesystem import read_json_file
from trak.utils.projects import db_get_project_details
from trak.utils.rich_toolkit import create_rich_toolkit_app
from trak.works.models import Work


def get_db_content() -> list[Record] | None:
    """
    Get the content in the database.
    """

    db_path = get_db_file_path()

    if not db_path:
        return None

    sessions_list = read_json_file(db_path)

    if not sessions_list:
        return None

    try:
        sessions_list = list(map(lambda session: Record(**session), sessions_list))
        return sessions_list
    except Exception:
        return None


def manage_field_in_json_file(
    file_path: Path, field_name: str, field_value: str | int | float | bool
):
    """
    Manage the content of a single object JSON file.
    """

    with open(file_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    if field_name:
        parsed_json[field_name] = field_value

    with open(file_path, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


#
# Database operations
#


def init_database(p: Path, initial_value: str = "[]") -> bool:
    """
    Initialize the trak database.
    """

    print("here!1")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write(initial_value)
        print("here!2")

        return True
    except OSError as error:
        print(error)
        return False


def add_session(record: Record):
    """
    Add a new session to the database.
    """

    db_content = get_db_content()
    if not db_content:
        return

    db_content.append(record)

    save_db(db_content)

    return True


def stop_trak_session() -> Record | None:
    """
    Stop tracking the current project.
    """

    db_content = get_db_content()
    if not db_content:
        return

    # Create a list of the running sessions
    current_sessions_indexes = [
        (index, record) for index, record in enumerate(db_content) if not record.end
    ]

    session_index = -1

    # Support multiple running sessions
    if len(current_sessions_indexes) > 1:
        project_propeties_options: list[Option] = [
            {"name": record.project, "value": index}
            for index, record in enumerate(db_content)
            if not record.end
        ]

        rt_app = create_rich_toolkit_app()
        session_index = rt_app.ask(
            title="Property", options=project_propeties_options, allow_filtering=True
        )

        if session_index is None:
            return

    elif len(current_sessions_indexes) == 1:
        session_index = current_sessions_indexes[0][0]

    if session_index > -1:
        db_content[session_index] = db_content[session_index]._replace(
            end=datetime.now().isoformat(timespec="seconds")
        )

        save_db(content=db_content)

        try:
            # Return the stopped record
            return db_content[session_index]
        except Exception:
            return
    else:
        return


def get_running_session() -> Record | None:
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    db_content = get_db_content()
    if not db_content:
        return

    # Create a list of the running sessions
    current_sessions = [record for record in db_content if not record.end]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return
    except KeyError:
        return

    if last_record.end == "":
        return last_record

    return


def delete_project_sessions(project_id: str) -> Record | None:
    """
    Delete all sessions of a project.
    """

    db_content = get_db_content()
    if not db_content:
        return

    project_sessions = [
        record for record in db_content if not record.project == project_id
    ]

    save_db(project_sessions)

    return


def get_session_by_id(id: int) -> Record | None:
    """Get latest, non current, session."""

    db_content = get_db_content()
    if not db_content:
        return

    try:
        return db_content[id]
    except Exception:
        return


def get_latest_session() -> tuple[Record, int] | None:
    """Get latest, non current, session."""

    db_content = get_db_content()
    if not db_content:
        return

    try:
        latest: Record = db_content[-1]
        index = len(db_content) - 1
        if not latest.end:
            latest = db_content[-2]
            index = len(db_content) - 2
    except Exception:
        return None

    return latest, index


def delete_session_by_id(id: int):
    session_to_delete = get_session_by_id(id)
    if not session_to_delete:
        return

    project = db_get_project_details(project_id=session_to_delete.project)
    if not project:
        print_error(
            title="Check the projects in your config.",
            text="You can try to use the doctor commands.",
        )
        return

    print_info(
        title="Session found",
        text=(
            f"ID {id}\n"
            f"Project {project.name}\n"
            f"Started {datetime.strptime(session_to_delete.start, "%Y-%m-%dT%H:%M:%S")}\n"
            f"Ended {datetime.strptime(session_to_delete.end, "%Y-%m-%dT%H:%M:%S")}.\n"
            f"Category {session_to_delete.category or "---"}.\n"
            f"Tag {session_to_delete.tag or "---" }.\n"
            f"Billable? {session_to_delete.billable}"
        ),
    )

    confirm = typer.confirm("Are you sure you want to delete this session?")
    if not confirm:
        raise typer.Abort()

    # Deletion
    db_content = get_db_content()
    if not db_content:
        return

    del db_content[id]
    save_db(db_content)

    return True


def get_record_collection(
    project: str,
    when: str = "",
    category: str = "",
    tag: str = "",
    billable: bool = False,
):
    """Get a collection of records, filtered by paramenters."""

    db_content = get_db_content()
    if not db_content:
        return

    records = [
        record for record in db_content if record.project == project and record.end
    ]

    if billable:
        records = [record for record in records if record.billable == billable]

    if category:
        records = [record for record in records if record.category == category]

    if tag:
        records = [record for record in records if record.tag == tag]

    if when:
        if when == "yesterday":
            records = [
                record
                for record in records
                if datetime.fromisoformat(record.end).date()
                == datetime.today().date() - timedelta(1)
            ]
        elif when == "today":
            records = [
                record
                for record in records
                if datetime.fromisoformat(record.end).date() == datetime.today().date()
            ]
        elif when == "week":
            records = [
                record
                for record in records
                if same_week(
                    datetime.fromisoformat(record.end).date().strftime("%Y%m%d"),
                )
            ]
        elif when == "month":

            def trunc_datetime(someDate):
                return someDate.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )

            records = [
                record
                for record in records
                if trunc_datetime(datetime.today())
                == trunc_datetime(datetime.fromisoformat(record.end))
            ]
        else:
            try:
                records = [
                    record
                    for record in records
                    if datetime.fromisoformat(record.end).date()
                    == datetime.fromisoformat(when).date()
                ]
            except Exception:
                print_error(
                    title="Invalid date",
                    text=(
                        "The provided date it's invalid.\n\n"
                        "Try with a date like 2034-10-08,"
                        " or the strings today, yesterday."
                    ),
                )

    table = Table(title=f"[bold]{project}[/bold]")

    table.add_column("Start", justify="right", style="green", no_wrap=True)
    table.add_column("End", style="orange3", no_wrap=True)
    table.add_column("Category", style="steel_blue1")
    table.add_column("Tag", style="steel_blue3")
    table.add_column("Hours", style="yellow", no_wrap=True)
    table.add_column("Billable")

    acc_seconds = 0

    for record in records:
        start_datetime = datetime.fromisoformat(record.start)
        end_datetime = datetime.fromisoformat(record.end)

        diff = end_datetime - start_datetime

        acc_seconds = acc_seconds + diff.seconds

        m, _ = divmod(diff.seconds, 60)
        h, m = divmod(m, 60)

        table.add_row(
            format_datetime_readable(record.start),
            format_datetime_readable(record.end),
            record.category or "---",
            record.tag or "---",
            f"{h}h {m}m",
            "✅" if record.billable else "",
        )

    console = Console()
    console.print(padding.Padding(table, (2, 0)))

    m, _ = divmod(acc_seconds, 60)
    h, m = divmod(m, 60)

    sum_panel = Panel(
        print_with_padding(f"[bold]{h}h {m}m[/bold]"), title="🧮 Total spent time"
    )
    print(sum_panel)

    return records


def show_json_file_content(file_path: Path):
    """Show the content of a JSON file."""

    with open(file_path, "r") as file:
        json_file_content = file.read()

    parsed_json = json.loads(json_file_content)
    print(parsed_json)


def overwrite_json_file(file_path: Path, content: dict | list[dict]):
    """Fill a JSON file with the provided content. It's a complete overwrite."""

    with open(file_path, "w+") as db:
        try:
            json.dump(content, db, indent=2, separators=(",", ": "))
            return True
        except Exception:
            print_error(text="Can't save the file.")
            return False


def save_db(content: list[Record]):
    """Save new content into the database file."""
    db_path = get_db_file_path()

    if db_path:
        content_dicts = [c._asdict() for c in content]

        with open(db_path, "w") as db:
            json.dump(content_dicts, db, indent=2, separators=(",", ": "))


def get_project_works(project_id: str):
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


def save_project_works(project_id: str, works: list[Work]):
    """Get the project works in the config by id."""

    works_path = get_works_path(project_id)

    if works_path is not None and works_path.exists() and works_path.is_file():
        with open(works_path, "w") as works_file:
            works_dicts = [w._asdict() for w in works]
            json.dump(works_dicts, works_file, indent=2, separators=(",", ": "))
