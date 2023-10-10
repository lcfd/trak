import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from rich import padding, print as rprint
from rich.panel import Panel

from trakcli.config import DB_FILE_PATH
from trakcli.utils.format_date import format_date
from trakcli.utils.print_with_padding import print_with_padding
from rich.console import Console
from rich.table import Table

from trakcli.utils.same_week import same_week

#
# Database operations
#


class Record(NamedTuple):
    project: str = ""
    start: str = ""
    end: str = ""
    billable: bool = False
    category: str = ""
    tag: str = ""


def add_track_field(record: Record):
    """..."""

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json.append(record._asdict())

    with open(DB_FILE_PATH, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def stop_track_field():
    """Stop tracking the current project."""

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)
    parsed_json[-1]["end"] = datetime.now().isoformat()

    with open(DB_FILE_PATH, "w") as db:
        json.dump(parsed_json, db, indent=2, separators=(",", ": "))


def tracking_already_started():
    """
    Check if there already is a record that is running.
    If it's already running return the record.
    """

    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()
    parsed_json = json.loads(db_content)

    try:
        last_record = parsed_json[-1]
    except IndexError:
        return False

    if last_record["end"] == "":
        return last_record

    return False


def get_current_session():
    with open(DB_FILE_PATH, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    try:
        last_record = parsed_json[-1]
    except IndexError:
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

    with open(DB_FILE_PATH, "r") as db:
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

    table.add_column("Start", justify="right", style="cyan", no_wrap=True)
    table.add_column("End", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Tag", style="magenta")
    table.add_column("Hours", style="magenta", no_wrap=True)
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


def check_if_database_exists():
    """Check if the json db files exists."""

    return Path.exists(DB_FILE_PATH)


def init_database(p: Path) -> int:
    """Create the application database."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write("[]")
        return 0
    except OSError:
        return 1
