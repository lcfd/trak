from datetime import datetime

from rich.table import Table

from trak.models import Record
from trak.utils.dates import format_date


def create_table_details(project: str, records: list[Record]):
    details_table = Table(title=f"Sessions for {project}")

    details_table.add_column("Start", style="green", no_wrap=True)
    details_table.add_column("End", style="orange3", no_wrap=True)
    details_table.add_column("Category", style="steel_blue1")
    details_table.add_column("Tag", style="steel_blue3")
    details_table.add_column("Hours", style="yellow", no_wrap=True)
    details_table.add_column("Billable")

    # Sort by start date
    records = sorted(records, key=lambda x: x.start)

    for record in records:
        record_start = record.start
        record_end = record.end or datetime.now().isoformat()

        h, m = 0, 0

        if record_start != "":
            start_datetime = datetime.fromisoformat(record_start)
            end_datetime = datetime.fromisoformat(record_end)

            diff = end_datetime - start_datetime

            m, _ = divmod(diff.seconds, 60)
            h, m = divmod(m, 60)

        details_table.add_row(
            format_date(record.start),
            format_date(record.end) if record.end != "" else "🏃 Ongoing",
            record.category or "---",
            record.tag or "---",
            f"{h}h {m}m" if record_start != "" else "",
            "✅" if record.billable else "",
        )

    return details_table


def create_table_title(
    today: bool | None = None,
    yesterday: bool | None = None,
    week: bool | None = None,
    month: bool | None = None,
    year: bool | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
):
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
