from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.table import Table

from trakcli.database.basic import get_db_content
from trakcli.report.commands.constants import ALL_PROJECTS
from trakcli.report.commands.types import (
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
from trakcli.works.database import get_project_works_from_config
from trakcli.works.messages.print_work import print_work


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

    project_id = projects_picker(project_id=project_id, archived=archived, all=True)

    if not project_id:
        return

    db_content = get_db_content()

    if db_content is None:
        print_error(
            title="Corrupted database",
            text="Check your database, you may have some broken records.",
        )
        return

    report_table_title = create_title(today, yesterday, week, month, year, start, end)

    main_table = Table(title=report_table_title)

    main_table.add_column("Project", style="cyan", no_wrap=True)
    main_table.add_column("Time spent", style="magenta")

    grouped = get_grouped_records(project_id, db_content)

    #
    # Accumulators
    #

    projects_data: list[ProjectData] = []
    total_acc_seconds = 0

    for g in grouped:
        if works:
            # If works is passed only billable records are considered.
            # All the time filters are ignored since they already are in the work.
            records = filter_records(
                records=grouped[g],
                billable=True,
                yesterday=None,
                today=None,
                week=None,
                month=None,
                start=None,
                end=None,
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

                m, _ = divmod(diff.seconds, 60)
                h, m = divmod(m, 60)

        total_acc_seconds += acc_seconds
        m, _ = divmod(acc_seconds, 60)
        h, m = divmod(m, 60)

        main_table.add_row(g, f"[bold]{h}h {m}m[/bold]")

        project_data: ProjectData = {
            "project": g,
            "details": None,
            "works": [],
            "records": records,
        }

        if len(records):
            if details:
                project_data["details"] = create_details(g, records)

            if works:
                project_works = get_project_works_from_config(g)
                if project_works is not None:
                    for work in project_works:
                        if work.done is not True:
                            project_data["works"].append(work)

        projects_data.append(project_data)

    # Spacing
    rprint("")

    # Add Total if all projects
    if project_id == ALL_PROJECTS:
        m, _ = divmod(total_acc_seconds, 60)
        h, m = divmod(m, 60)

        main_table.add_section()
        main_table.add_row("Total", f"[bold]{h}h {m}m[/bold]")

    # Print summary report table
    rprint(main_table)

    # Details --details -d
    # Print detailed data
    for data in projects_data:
        if data["details"] is not None:
            rprint("")
            rprint(data["details"])

        project_works = data["works"]
        if project_works is not None and works is True:
            if len(project_works):
                for pw in project_works:
                    start_date_string = pw.from_date
                    end_date_string = pw.to_date
                    start_date = datetime.strptime(start_date_string, "%Y-%m-%dT%H:%M")
                    end_date = datetime.strptime(end_date_string, "%Y-%m-%dT%H:%M")

                    # Print the data for a work
                    filtered_records = filter_records(
                        records=data.get("records"), start=start_date, end=end_date
                    )

                    acc_seconds = 0

                    for record in filtered_records:
                        record_start = record.start
                        record_end = record.end

                        if record_start != "" and record_end != "":
                            start_datetime = datetime.fromisoformat(record_start)
                            end_datetime = datetime.fromisoformat(record_end)

                            diff = end_datetime - start_datetime

                            acc_seconds = acc_seconds + diff.seconds

                            m, _ = divmod(diff.seconds, 60)
                            h, m = divmod(m, 60)

                    m, _ = divmod(acc_seconds, 60)
                    h, m = divmod(m, 60)

                    print_work(
                        work=pw,
                        start_date=start_date,
                        end_date=end_date,
                        project=data["project"],
                        hours=h,
                        minutes=m,
                        work_time=pw.time,
                        totSeconds=acc_seconds,
                    )
