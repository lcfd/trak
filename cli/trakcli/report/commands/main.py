from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.table import Table

from trakcli.database.basic import get_db_content
from trakcli.report.functions.create_details_table import create_details_table
from trakcli.report.functions.filter_records import filter_records
from trakcli.report.functions.get_grouped_records import get_grouped_records
from trakcli.report.functions.get_table_title import get_table_title

ALL_PROJECTS = "all"


def report_project(
    project: Annotated[str, typer.Argument()] = ALL_PROJECTS,
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
    details: Annotated[
        bool,
        typer.Option(
            "--details",
            "-d",
            help="Show all sessions that occurred in the chosen period in detail.",
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
        Optional[datetime],
        typer.Option(
            "--start",
            help="Start date (e.g. 2023-10-08) for the time range. If --end is not provided, trak will report the data for the provided date.",
            formats=["%Y-%m-%d"],
        ),
    ] = None,
    end: Annotated[
        Optional[datetime],
        typer.Option(
            "--end",
            help="End date (e.g. 2023-11-24) for the time range. Won't work without the start flag.",
            formats=["%Y-%m-%d"],
        ),
    ] = None,
):
    """Get reports for your projects."""

    db_content = get_db_content()

    report_table_title = get_table_title(
        today, yesterday, week, month, year, start, end
    )

    main_table = Table(title=report_table_title)

    main_table.add_column("🏷️  Project", style="cyan", no_wrap=True)
    main_table.add_column("🧮 Time spent", style="magenta")

    grouped = get_grouped_records(project, db_content, ALL_PROJECTS)
    records = []
    details_tables = []
    total_acc_seconds = 0

    for g in grouped:
        records = filter_records(
            grouped[g], billable, yesterday, today, week, month, start, end
        )

        acc_seconds = 0

        for record in records:
            record_start = record.get("start", "")
            record_end = record.get("end", "")

            if record_start != "" and record_end != "":
                start_datetime = datetime.fromisoformat(record_start)
                end_datetime = datetime.fromisoformat(record_end)

                diff = end_datetime - start_datetime

                acc_seconds = acc_seconds + diff.seconds

                m, _ = divmod(diff.seconds, 60)
                h, m = divmod(m, 60)

        total_acc_seconds += acc_seconds
        m, _ = divmod(acc_seconds, 60)
        h, m = divmod(m, 60)

        main_table.add_row(g, f"[bold]{h}h {m}m[/bold]")

        if details and len(records):
            details_tables.append(create_details_table(g, records))

    rprint("")

    # Add Total if all projects
    if project == ALL_PROJECTS:
        m, _ = divmod(total_acc_seconds, 60)
        h, m = divmod(m, 60)

        main_table.add_section()
        main_table.add_row("Total", f"[bold]{h}h {m}m[/bold]")

    # Print summary report table
    rprint(main_table)

    # Print details
    for details_table in details_tables:
        rprint("")
        rprint(details_table)
