from datetime import datetime, timedelta
from typing import Annotated
from rich.panel import Panel

import typer
from rich import print as rprint
from rich.table import Table

from trakcli.database.basic import get_db_content
from trakcli.utils.print_with_padding import print_with_padding
from trakcli.utils.same_week import same_week

ALL_PROJECTS = "all"


def report(
    project: Annotated[str, typer.Argument()] = ALL_PROJECTS,
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
    today: Annotated[
        bool,
        typer.Option(
            "--today",
            help="Consider only today's records.",
        ),
    ] = False,
    yesterday: Annotated[
        bool,
        typer.Option(
            "--yesterday",
            help="Consider only this month's records.",
        ),
    ] = False,
    week: Annotated[
        bool,
        typer.Option(
            "--week",
            help="Consider only this week's records.",
        ),
    ] = False,
    month: Annotated[
        bool,
        typer.Option(
            "--month",
            help="Consider only this month's records.",
        ),
    ] = False,
    year: Annotated[
        bool,
        typer.Option(
            "--year",
            help="Consider only this year's records.",
        ),
    ] = False,
    start: Annotated[
        str,
        typer.Option(
            "--start",
            help="Start date (e.g. 2023-10-08) for the time range. If --end is not provided, trak will report the data for the provided date.",
        ),
    ] = "",
    end: Annotated[
        str,
        typer.Option(
            "--end",
            help="End date (e.g. 2023-11-24) for the time range. Won't work without the start flag.",
        ),
    ] = "",
):
    """Get reports for your projects."""

    parsed_json = get_db_content()

    table_title = "Report"
    if today:
        table_title += " for today"
    elif yesterday:
        table_title += " for yestarday"
    elif week:
        table_title += " for this week"
    elif month:
        table_title += " for this month"
    elif year:
        table_title += " for this year"
    elif start and end == "":
        table_title += f" for the day {start}"
    elif start and end:
        table_title += f" for the period from {start} to {end}"

    table = Table(title=table_title)

    table.add_column("🏷️  Project", style="cyan", no_wrap=True)
    table.add_column("🧮 Time spent", style="magenta")

    actual_month = datetime.today().month
    actual_year = datetime.today().year

    try:
        datetime.fromisoformat(start).date()
        datetime.fromisoformat(end).date()
    except ValueError:
        rprint(
            Panel(
                title="🔴 Invalid date",
                renderable=print_with_padding(
                    (
                        "The provided date it's invalid."
                        "\n\n"
                        f"Try with a date like {datetime.now().date()}."
                    )
                ),
            )
        )

        return

    grouped = {}

    for record in parsed_json:
        record_project = record.get("project", False)
        if record_project:
            if record_project == project or project == ALL_PROJECTS:
                if isinstance(grouped.get(record_project, False), list):
                    grouped[record_project].append(record)
                else:
                    grouped[record_project] = [record]

    for g in grouped:
        records = grouped[g]

        if billable:
            records = [
                record for record in grouped[g] if record["billable"] == billable
            ]

        if yesterday:
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                == datetime.today().date() - timedelta(1)
            ]
        elif today:
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                == datetime.today().date()
            ]
        elif week:
            records = [
                record
                for record in records
                if same_week(
                    datetime.fromisoformat(record["end"]).date().strftime("%Y%m%d"),
                )
            ]
        elif month:
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).month == actual_month
                and datetime.fromisoformat(record["end"]).year == actual_year
            ]
        elif start and end == "":
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                == datetime.fromisoformat(start).date()
            ]
        elif start and end:
            records = [
                record
                for record in records
                if datetime.fromisoformat(record["end"]).date()
                >= datetime.fromisoformat(start).date()
                and datetime.fromisoformat(record["end"]).date()
                <= datetime.fromisoformat(end).date()
            ]

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

        table.add_row(g, f"[bold]{h}h {m}m[/bold]")

    rprint("")
    rprint(table)
