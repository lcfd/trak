import json
from datetime import datetime, timedelta
from pathlib import Path

import questionary
from rich import padding
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trakcli.config.main import (
    get_db_file_path,
)
from trakcli.database.models import Record
from trakcli.utils.format_date import format_date
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.utils.same_week import same_week
from trakcli.utils.styles_questionary import questionary_style_select

#
# Database operations
#


def init_database(p: Path, initial_value: str = "[]") -> int:
    """Initialize the trak database."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write(initial_value)
        return 0
    except OSError:
        return 1


def add_session(record: Record):
    """Add a new session."""

    db_path = get_db_file_path()

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json.append(record._asdict())

    with open(db_path, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def stop_trak_session():
    """Stop tracking the current project."""

    db_path = get_db_file_path()

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    # Create a list of the running sessions
    current_sessions_indexes = [
        (index, record) for index, record in enumerate(parsed_json) if not record["end"]
    ]

    session_index = -1

    if len(current_sessions_indexes) > 1:
        # Support stopping a session when there are multiple running sessions
        choices = [
            questionary.Choice(title=record["project"], value=index)
            for index, record in enumerate(parsed_json)
            if not record["end"]
        ]

        session_index = questionary.select(
            "Select a session:",
            choices=choices,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

    elif len(current_sessions_indexes) == 1:
        session_index = current_sessions_indexes[0][0]

    if session_index > -1:
        parsed_json[session_index]["end"] = datetime.now().isoformat()

        with open(db_path, "w") as db:
            json.dump(parsed_json, db, indent=2, separators=(",", ": "))

        # Return the stopped record
        try:
            return Record(**parsed_json[session_index])
        except Exception:
            return


def tracking_already_started() -> Record | bool:
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    db_path = get_db_file_path()

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    # Create a list of the running sessions
    current_sessions = [record for record in parsed_json if not record["end"]]

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

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    # Create a list of the running sessions
    current_sessions = [record for record in parsed_json if not record["end"]]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return False
    except KeyError:
        return False

    if last_record["end"] == "":
        return Record(**last_record)

    return False


def get_current_session():
    """Get the current session from records in database."""

    db_path = get_db_file_path()

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    # Create a list of the running sessions
    current_sessions = [record for record in parsed_json if not record["end"]]

    try:
        last_record = current_sessions[-1]
    except IndexError:
        return False
    except KeyError:
        return False

    if last_record["end"] == "":
        return last_record

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

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    records = [
        record
        for record in parsed_json
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
                rprint(
                    Panel(
                        title="🔴 Invalid date",
                        renderable=print_with_padding(
                            """The provided date it's invalid.

Try with a date like 2023-10-08, or the strings today, yesterday."""
                        ),
                    )
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
    rprint(sum_panel)

    return records
