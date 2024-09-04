from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.table import Table

from trakcli.database.basic import get_db_content
from trakcli.report.constants import ALL_PROJECTS
from trakcli.report.functions.print import print_details_and_works
from trakcli.report.types import (
    ArchivedOption,
    BillableOption,
    DetailsOption,
    EndOption,
    MonthOption,
    ProjectData,
    StartOption,
    TodayOption,
    WeekOption,
    WorksOption,
    YearOption,
    YesterdayOption,
)
from trakcli.report.functions.filter_records import filter_records
from trakcli.report.functions.get_grouped_records import get_grouped_records
from trakcli.report.functions.table import create_details, create_title
from trakcli.utils.messages import print_error
from trakcli.utils.projects_picker import projects_picker
from trakcli.utils.time import get_hours_minutes_from_seconds
from trakcli.works.database import get_project_works_from_config_folder


def report_project(
    project_id: Annotated[Optional[str], typer.Argument()] = None,
    billable: BillableOption = False,
    works: WorksOption = False,
    details: DetailsOption = False,
    today: TodayOption = False,
    yesterday: YesterdayOption = False,
    week: WeekOption = False,
    month: MonthOption = False,
    year: YearOption = False,
    start: StartOption = None,
    end: EndOption = None,
    archived: ArchivedOption = False,
):
    """
    Get reports for your projects.
    The projects will be get by the configuration in the .trak folder.
    """

    # Get project id
    project_id = projects_picker(project_id=project_id, archived=archived, all=True)
    if not project_id:
        return

    # Get database content
    db_content = get_db_content()
    if db_content is None:
        print_error(
            title="Corrupted database",
            text="Check your database, you may have some broken records.",
        )
        return

    # Table
    report_table_title = create_title(today, yesterday, week, month, year, start, end)
    main_table = Table(title=report_table_title)
    main_table.add_column("Project", style="cyan", no_wrap=True)
    main_table.add_column("Time spent", style="magenta")

    # Group data
    grouped = get_grouped_records(project_id, db_content)

    # Accumulators

    projects_data: list[ProjectData] = []
    total_acc_seconds = 0

    for g in grouped:
        if works:
            # If works is passed only billable records are considered.
            records = filter_records(
                records=grouped[g],
                billable=True,
                start=start,
                end=end,
                yesterday=None,
                today=None,
                week=None,
                month=None,
            )
        else:
            records = filter_records(
                grouped[g], billable, yesterday, today, week, month, start, end
            )

        acc_seconds = 0

        for record in records:
            record_start = record.start
            record_end = record.end

            if record_start != "" and record_end != "":
                start_datetime = datetime.fromisoformat(record_start)
                end_datetime = datetime.fromisoformat(record_end)

                diff = end_datetime - start_datetime

                acc_seconds = acc_seconds + diff.seconds

                h, m = get_hours_minutes_from_seconds(diff.seconds)

        total_acc_seconds += acc_seconds
        h, m = get_hours_minutes_from_seconds(acc_seconds)

        main_table.add_row(g, f"[bold]{h}h {m}m[/bold]")

        project_data: ProjectData = {
            "project": g,
            "details": None,
            "works": [],
            "records": records,
        }

        if len(records):
            # Add details to output
            if details:
                project_data["details"] = create_details(g, records)

            # Add works to output
            if works:
                project_works = get_project_works_from_config_folder(g)
                if project_works is not None:
                    for work in project_works:
                        if work.done is not True:
                            project_data["works"].append(work)

        projects_data.append(project_data)

    # Add Total of timings if project id is `all`
    if project_id == ALL_PROJECTS:
        h, m = get_hours_minutes_from_seconds(total_acc_seconds)

        main_table.add_section()
        main_table.add_row("Total", f"[bold]{h}h {m}m[/bold]")

    # Print summary report table
    rprint("")
    rprint(main_table)

    print_details_and_works(projects_data, works)
