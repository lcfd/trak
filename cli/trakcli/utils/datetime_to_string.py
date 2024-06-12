from datetime import datetime


def datetime_to_string(dt: datetime):
    return dt.strftime("%Y-%m-%dT%H:%M")
