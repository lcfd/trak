from datetime import datetime


def datetime_to_string(dt: datetime):
    """Converta date to string with %Y-%m-%dT%H:%M format."""
    return dt.strftime("%Y-%m-%dT%H:%M")


def format_date(str_date: str):
    """Format string date to %Y-%m-%d, %H:%M."""
    d = datetime.fromisoformat(str_date)
    return d.strftime("%Y-%m-%d, %H:%M")


def same_week(dateString):
    """Returns true if a dateString in %Y%m%d format is part of the current week."""

    d1 = datetime.strptime(dateString, "%Y%m%d")
    d2 = datetime.today()
    return d1.isocalendar()[1] == d2.isocalendar()[1] and d1.year == d2.year
