from datetime import datetime
from typing import Annotated, Optional

import questionary
import typer
from rich import print as rprint
from rich.progress import Progress
from rich.table import Table

from trakcli.database.basic import get_db_content
from trakcli.projects.database import get_projects_from_config
from trakcli.projects.utils.print_missing_project import print_missing_project
from trakcli.projects.utils.print_no_projects import print_no_projects
from trakcli.report.functions.create_details_table import create_details_table
from trakcli.report.functions.filter_records import filter_records
from trakcli.report.functions.get_grouped_records import get_grouped_records
from trakcli.report.functions.get_table_title import get_table_title
from trakcli.utils.messages.print_error import print_error
from trakcli.utils.styles_questionary import questionary_style_select
from trakcli.works.database import get_project_works_from_config

ALL_PROJECTS = "all"


def report_project(
    project: Annotated[Optional[str], typer.Argument()] = None,
    billable: Annotated[
        bool,
        typer.Option(
            "--billable",
            "-b",
            help="Consider only the billable records.",
        ),
    ] = False,
    works: Annotated[
        bool,
        typer.Option(
            "--works",
            help="Show the works related to the project.",
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
            "-y",
            help="Consider only this month's records.",
        ),
    ] = False,
    week: Annotated[
        bool,
        typer.Option(
            "--week",
            "-w",
            help="Consider only this week's records.",
        ),
    ] = False,
    month: Annotated[
        bool,
        typer.Option(
            "--month",
            "-m",
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
            "-s",
            help="Start date (e.g. 2023-10-08) for the time range. If --end is not provided, trak will report the data for the provided date.",
            formats=["%Y-%m-%d"],
        ),
    ] = None,
    end: Annotated[
        Optional[datetime],
        typer.Option(
            "--end",
            "-e",
            help="End date (e.g. 2023-11-24) for the time range. Won't work without the start flag.",
            formats=["%Y-%m-%d"],
        ),
    ] = None,
    archived: Annotated[
        Optional[bool],
        typer.Option(
            "--archived",
            "-a",
            help="Show archived projects in lists.",
        ),
    ] = False,
):
    """
    Get reports for your projects.
    The projects will be get by the configuration in the .trak folder.
    """

    projects_in_config = get_projects_from_config(archived)

    projects_in_config.append(ALL_PROJECTS)

    # Check if there are configured projects
    if not len(projects_in_config):
        print_no_projects()
        return

    # Provide the list of prjects to the user
    if not project:
        project = questionary.select(
            "Select a project:",
            choices=projects_in_config,
            pointer="• ",
            show_selected=True,
            style=questionary_style_select,
        ).ask()

        if not project:
            return

    # Check if the project exists
    if not project or project not in projects_in_config:
        print_missing_project(projects_in_config)
        return

    db_content = get_db_content()

    if db_content is None:
        print_error(
            title="Corrupted database",
            text="Check your database, you may have some broken records.",
        )
        return

    report_table_title = get_table_title(
        today, yesterday, week, month, year, start, end
    )

    main_table = Table(title=report_table_title)

    main_table.add_column("Project", style="cyan", no_wrap=True)
    main_table.add_column("Time spent", style="magenta")

    grouped = get_grouped_records(project, db_content, ALL_PROJECTS)

    #
    # Accumulators
    #

    projects_data = []
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

        project_data = {"project": g, "details": None, "works": [], "records": records}

        if len(records):
            if details:
                project_data["details"] = create_details_table(g, records)

            if works:
                project_works = get_project_works_from_config(g)
                if project_works is not None:
                    for work in project_works:
                        if work.get("done") is not True:
                            project_data["works"].append(work)

        projects_data.append(project_data)

    # Spacing
    rprint("")

    # Add Total if all projects
    if project == ALL_PROJECTS:
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
                    start_date_string = pw.get("from_date")
                    end_date_string = pw.get("to_date")
                    start_date = datetime.strptime(start_date_string, "%Y-%m-%dT%H:%M")
                    end_date = datetime.strptime(end_date_string, "%Y-%m-%dT%H:%M")

                    # Print the data for a work
                    filtered_records = filter_records(
                        records=data.get("records"), start=start_date, end=end_date
                    )

                    acc_seconds = 0

                    work_time = pw.get("time", None)

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

                    # TODO: to extract in a separated function

                    rprint("")
                    rprint("┏━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    rprint(f"┃ [blue]Work {pw['id']}")
                    rprint(f"┃ [green]{pw['name']}")
                    rprint("┃ ---")
                    rprint(f"┃ start: {start_date}, end: {end_date}")
                    rprint(f"┃ project: {data['project']}")
                    rprint("┡━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    rprint("│ ")
                    with Progress() as progress:
                        rprint("│ [blue]Used time budget:")
                        rprint(f"│ Total: {pw['time']} hours")
                        rprint(f"│ Used: {h} hours {m} minutes ")
                        task = progress.add_task("", total=work_time * 3600)
                        progress.update(task, advance=acc_seconds)
                    rprint("│ ")
                    with Progress() as progress:
                        rprint("│ [blue]Closeness to the deadline:")
                        start = datetime.strptime(pw.get("from_date"), "%Y-%m-%dT%H:%M")
                        end = datetime.strptime(pw.get("to_date"), "%Y-%m-%dT%H:%M")
                        work_duration_days = (end - start).days
                        today_to_deadline_days = (end - datetime.today()).days
                        today_from_start_days = (datetime.today() - start).days
                        rprint(f"│ Total: {work_duration_days} days")
                        rprint(f"│ Remaining: {today_to_deadline_days} days")
                        task = progress.add_task("", total=work_duration_days)
                        progress.update(task, advance=today_from_start_days)
                    rprint("│ ")
                    rprint("│ [blue]Workable hours (8h/day) until deadline:")
                    today_to_deadline_days = (end - datetime.today()).days
                    rprint(
                        f"│ {(today_to_deadline_days  *24) / 8} hours in {today_to_deadline_days} days"
                    )
                    rprint("│ ")
                    rprint("│ [blue]Value of your work so far:")
                    rprint(f"│ {pw['rate']*h}€")
                    rprint("│ ")
                    rprint("└━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
