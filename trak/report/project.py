from datetime import datetime

from rich import print as rprint
from rich.table import Table

from trak.database import get_db_content
from trak.report.annotations import (
    ArchivedOption,
    BillableOption,
    EndOption,
    MonthOption,
    ProjectIdOption,
    StartOption,
    TodayOption,
    WeekOption,
    YearOption,
    YesterdayOption,
)
from trak.constants import ALL_PROJECTS
from trak.report.utils.get_grouped_records import get_grouped_records
from trak.report.utils.table import create_table_title
from trak.utils.base_messages import print_error
from trak.utils.filters import filter_records
from trak.utils.projects import project_exists, projects_picker
from trak.utils.time import get_hours_minutes_from_seconds


def report_project(
    project_id: ProjectIdOption = None,
    billable: BillableOption = False,
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
    Show reports for your projects.
    """

    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

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
    report_table_title = create_table_title(
        today, yesterday, week, month, year, start, end
    )
    main_table = Table(title=report_table_title)
    main_table.add_column("Project", style="cyan", no_wrap=True)
    main_table.add_column("Time spent", style="magenta")

    # Group data
    grouped = get_grouped_records(project_id, db_content)

    # Accumulators
    total_acc_seconds = 0

    for g in grouped:
        records = filter_records(
            records=grouped[g],
            billable=billable,
            yesterday=yesterday,
            today=today,
            week=week,
            month=month,
            year=year,
            start=start,
            end=end,
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

    # Add Total of timings if project project_id is `all`
    if project_id == ALL_PROJECTS:
        h, m = get_hours_minutes_from_seconds(total_acc_seconds)

        main_table.add_section()
        main_table.add_row("Total", f"[bold]{h}h {m}m[/bold]")

    # Print summary report table
    rprint("")
    rprint(main_table)
