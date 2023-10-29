# import json
# from rich.panel import Panel
# from rich.table import Table
from datetime import datetime, timedelta
import json
from typing import Annotated
from rich.panel import Panel

import typer
from trakcli.config.main import get_db_file_path

from trakcli.database.database import get_record_collection

from rich import print as rprint

from trakcli.utils.print_with_padding import print_with_padding
from trakcli.utils.same_week import same_week

# from trakcli.config.main import CONFIG_FILE_PATH, get_config, get_db_file_path
# from trakcli.config.models import Project
# from trakcli.utils.print_with_padding import print_with_padding
#
# from trakcli.projects.database import (
#     get_projects_from_config,
#     get_projects_from_db,
# )

app = typer.Typer()


@app.command()
def all(
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
    when: Annotated[
        str,
        typer.Option(
            "--when",
            "-w",
            help="Look for records in a specific date or range by keyword. \
Values may be: \
- today \
- yesterday \
- month: the current month \
- yyyy-mm-dd: like 2023-10-08",
        ),
    ] = "",
):
    """
    Report stats for all projects.
    """

    db_path = get_db_file_path()

    with open(db_path, "r") as db:
        db_content = db.read()

    parsed_json = json.loads(db_content)

    grouped = {}

    for record in parsed_json:
        project = record.get("project", False)
        if project:
            del record["project"]
            if isinstance(grouped.get(project, False), list):
                grouped[project].append(record)
            else:
                grouped[project] = [record]

    for g in grouped:
        records = grouped[g]

        if billable:
            records = [
                record for record in grouped[g] if record["billable"] == billable
            ]

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

        acc_seconds = 0

        for record in records:
            start_datetime = datetime.fromisoformat(record["start"])
            end_datetime = datetime.fromisoformat(record["end"])

            diff = end_datetime - start_datetime

            acc_seconds = acc_seconds + diff.seconds

            m, _ = divmod(diff.seconds, 60)
            h, m = divmod(m, 60)

        m, _ = divmod(acc_seconds, 60)
        h, m = divmod(m, 60)

        sum_panel = Panel(
            print_with_padding(f"[bold]{h}h {m}m[/bold]"),
            title=f"🧮 Total spent time on {g}",
        )

        rprint(sum_panel)


@app.command()
def single(
    project: str,
    when: Annotated[
        str,
        typer.Option(
            "--when",
            "-w",
            help="Look for records in a specific date or range by keyword. \
Values may be: \
- today \
- yesterday \
- month: the current month \
- yyyy-mm-dd: like 2023-10-08",
        ),
    ] = "",
    category: Annotated[str, typer.Option("--category", "-c")] = "",
    tag: Annotated[str, typer.Option("--tag", "-t")] = "",
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
):
    """
    Report stats for single projects.
    """

    get_record_collection(
        project=project, billable=billable, category=category, tag=tag, when=when
    )
