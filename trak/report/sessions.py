from rich import print

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
from trak.utils.get_grouped_records import get_grouped_records
from trak.utils.table import create_table_details
from trak.utils.base_messages import print_error
from trak.utils.filters import filter_records
from trak.utils.projects import project_exists, projects_picker


def report_sessions(
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
    Show reports for your sessions.
    """

    if (
        isinstance(project_id, str)
        and not project_exists(project_id)
        and project_id != ALL_PROJECTS
    ):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    # Get project id
    project_id = projects_picker(project_id=project_id, archived=archived, all=True)
    if not project_id:
        return

    # Get database content
    db_content = get_db_content()
    if db_content is None:
        print_error(text="Check your database, you may have some broken records.")
        return

    # Group data
    grouped = get_grouped_records(project_id, db_content)

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

        if len(records):
            print("")
            print(create_table_details(g, records))
