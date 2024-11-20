from datetime import datetime, timedelta


def add_method(
    date: datetime,
    hours: int | None,
    minutes: int | None,
) -> tuple[datetime, datetime]:
    """
    Add hours and minutes to the provided date.
    date has precence over today.
    """

    # Defaults
    start_timedate = date
    end_timedate = start_timedate

    # Add hours and minutes
    if hours or minutes:
        if hours:
            end_timedate = end_timedate + timedelta(hours=hours)
        if minutes:
            end_timedate = end_timedate + timedelta(minutes=minutes)

    return start_timedate, end_timedate


def sub_method(
    hours: int | None,
    minutes: int | None,
) -> tuple[datetime, datetime]:
    """
    Subtract hours and minutes from current time (now).
    """

    # Defaults
    end_timedate = datetime.today()
    start_timedate = datetime.today()

    # Add hours and minutes
    if hours or minutes:
        if hours:
            end_timedate = end_timedate - timedelta(hours=hours)
        if minutes:
            end_timedate = end_timedate - timedelta(minutes=minutes)

    return start_timedate, end_timedate
