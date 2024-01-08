from datetime import datetime


def get_table_title(
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
