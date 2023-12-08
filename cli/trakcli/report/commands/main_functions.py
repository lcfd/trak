from datetime import datetime, timedelta

from rich.table import Table

from trakcli.utils.format_date import format_date
from trakcli.utils.same_week import same_week


def get_table_title(today, yesterday, week, month, year, start, end):
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

    return table_title


def create_details_table(project, records):
    details_table = Table(title=f"Sessions for {project}")

    details_table.add_column("Start", style="green", no_wrap=True)
    details_table.add_column("End", style="orange3", no_wrap=True)
    details_table.add_column("Category", style="steel_blue1")
    details_table.add_column("Tag", style="steel_blue3")
    details_table.add_column("Hours", style="yellow", no_wrap=True)
    details_table.add_column("Billable")

    for record in records:
        record_start = record.get("start", "")
        record_end = record.get("end", "") or datetime.now().isoformat()

        h, m = 0, 0

        if record_start != "":
            start_datetime = datetime.fromisoformat(record_start)
            end_datetime = datetime.fromisoformat(record_end)

            diff = end_datetime - start_datetime

            m, _ = divmod(diff.seconds, 60)
            h, m = divmod(m, 60)

        details_table.add_row(
            format_date(record["start"]),
            format_date(record["end"]) if record["end"] != "" else "🏃 Ongoing",
            record["category"] or "---",
            record["tag"] or "---",
            f"{h}h {m}m" if record_start != "" else "",
            "✅" if record["billable"] else "",
        )

    return details_table


def get_grouped_records(project, records, all):
    grouped = {}
    for record in records:
        record_project = record.get("project", False)

        if record_project:
            if record_project == project or project == all:
                if isinstance(grouped.get(record_project, False), list):
                    grouped[record_project].append(record)
                else:
                    grouped[record_project] = [record]

    return grouped


def filter_records(records, billable, yesterday, today, week, month, start, end):
    actual_month = datetime.today().month
    actual_year = datetime.today().year

    if billable:
        records = [record for record in records if record["billable"] == billable]

    # Only one time filer type is allowed
    if yesterday:
        records = [
            record
            for record in records
            if record["end"]
            and datetime.fromisoformat(record["end"]).date()
            == datetime.today().date() - timedelta(1)
        ]
    elif today:
        records = [
            record
            for record in records
            if record["end"]
            and datetime.fromisoformat(record["end"]).date() == datetime.today().date()
        ]
    elif week:
        records = [
            record
            for record in records
            if record["end"]
            and same_week(
                datetime.fromisoformat(record["end"]).date().strftime("%Y%m%d"),
            )
        ]
    elif month:
        records = [
            record
            for record in records
            if record["start"]
            and record["end"]
            and datetime.fromisoformat(record["end"]).month == actual_month
            and datetime.fromisoformat(record["end"]).year == actual_year
        ]
    elif start is not None and end is None:
        records = [
            record
            for record in records
            if record.get("end", "") != ""
            and datetime.fromisoformat(record["end"]).date() == start.date()
        ]
    elif start is not None and end is not None:
        records = [
            record
            for record in records
            if record.get("end", "") != ""
            and datetime.fromisoformat(record["end"]).date() >= start.date()
            and datetime.fromisoformat(record["end"]).date() <= end.date()
        ]

    return records
