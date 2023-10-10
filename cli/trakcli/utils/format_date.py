from datetime import datetime


def format_date(str_date: str):
    d = datetime.fromisoformat(str_date)
    return d.strftime("%Y-%m-%d, %H:%M")
