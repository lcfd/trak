import json
from datetime import datetime, timedelta
from pathlib import Path

import questionary
from rich import padding, print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trakcli.config.get_db_file_path import get_db_file_path
from trakcli.database.filesystem import read_json_file
from trakcli.database.models import Record
from trakcli.utils.dates import format_date, same_week
from trakcli.utils.messages import print_error
from trakcli.utils.messages import print_with_padding
from trakcli.utils.questionary import questionary_style_select

#
# Database operations
#


def init_database(p: Path, initial_value: str = "[]") -> bool:
    """Initialize the trak database."""

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
    """Add a new session to the database."""

    db_path = get_db_file_path()

    if not db_path:
        return False

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json.append(record._asdict())

    with open(db_path, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))

    return True


def stop_trak_session():
    """Stop tracking the current project."""

    db_path = get_db_file_path()

    if not db_path:
        return False

    db_content = read_json_file(db_path)

    if not db_content:
        return False

    # Create a list of the running sessions
    current_sessions_indexes = [
        (index, record) for index, record in enumerate(db_content) if not record["end"]
    ]

    session_index = -1

    if len(current_sessions_indexes) > 1:
        # Support stopping a session when there are multiple running sessions
        choices = [
            questionary.Choice(title=record["project"], value=index)
            for index, record in enumerate(db_content)
            if not record["end"]
        ]

        session_index = questionary.select(
            "Select a session:",
            choices=choices,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if session_index is None:
            return False

    elif len(current_sessions_indexes) == 1:
        session_index = current_sessions_indexes[0][0]

    if session_index > -1:
        db_content[session_index]["end"] = datetime.now().isoformat()

        with open(db_path, "w") as db:
            json.dump(db_content, db, indent=2, separators=(",", ": "))

        # Return the stopped record
        try:
            return Record(**db_content[session_index])
        except Exception:
            return False
    else:
        return False


def tracking_already_started() -> Record | bool:
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    db_path = get_db_file_path()

    if not db_path:
        return False

    db_content = read_json_file(db_path)

    if not db_content:
        return False

    # Create a list of the running sessions
    current_sessions = [record for record in db_content if not record["end"]]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return False
    except KeyError:
        return False

    if last_record["end"] == "":
        try:
            return Record(**last_record)
        except Exception:
            return False

    return False


def get_current_session_started() -> Record | bool:
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    db_path = get_db_file_path()

    if not db_path:
        return False

    db_content = read_json_file(db_path)

    if not db_content:
        return False

    # Create a list of the running sessions
    current_sessions = [record for record in db_content if not record["end"]]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return False
    except KeyError:
        return False

    if last_record["end"] == "":
        return Record(**last_record)

    return False


def get_current_session() -> Record | bool:
    """Get the current session from records in database."""

    db_path = get_db_file_path()

    if not db_path:
        return False

    db_content = read_json_file(db_path)

    if not db_content:
        return False

    # Create a list of the running sessions
    current_sessions = [record for record in db_content if not record["end"]]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return False
    except KeyError:
        return False

    if last_record["end"] == "":
        return Record(**last_record)

    return False


def get_record_collection(
    project: str,
    when: str = "",
    category: str = "",
    tag: str = "",
    billable: bool = False,
):
    """Get a collection of records, filtered by paramenters."""

    db_path = get_db_file_path()

    if not db_path:
        return False

    db_content = read_json_file(db_path)

    if not db_content:
        return False

    records = [
        record
        for record in db_content
        if record["project"] == project and record["end"]
    ]

    if billable:
        records = [record for record in records if record["billable"] == billable]

    if category:
        records = [record for record in records if record["category"] == category]

    if tag:
        records = [record for record in records if record["tag"] == tag]

    if when:
        if when == "yesterday":
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                == datetime.today().date() - timedelta(1)
            ]
        elif when == "today":
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                == datetime.today().date()
            ]
        elif when == "week":
            records = [
                record
                for record in records
                if same_week(
                    datetime.fromisoformat(record["end"]).date().strftime("%Y%m%d"),
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
                == trunc_datetime(datetime.fromisoformat(record["end"]))
            ]
        else:
            try:
                records = [
                    record
                    for record in records
                    if datetime.fromisoformat(record["end"]).date()
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
        start_datetime = datetime.fromisoformat(record["start"])
        end_datetime = datetime.fromisoformat(record["end"])

        diff = end_datetime - start_datetime

        acc_seconds = acc_seconds + diff.seconds

        m, _ = divmod(diff.seconds, 60)
        h, m = divmod(m, 60)

        table.add_row(
            format_date(record["start"]),
            format_date(record["end"]),
            record["category"] or "---",
            record["tag"] or "---",
            f"{h}h {m}m",
            "✅" if record["billable"] else "",
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
