from datetime import datetime, timedelta

from trakcli.database.models import Record
from trakcli.utils.same_week import same_week


def filter_records(
    records: list[Record],
    billable=None,
    yesterday=None,
    today=None,
    week=None,
    month=None,
    start=None,
    end=None,
) -> list[Record]:
    actual_month = datetime.today().month
    actual_year = datetime.today().year

    if billable:
        records = [record for record in records if record.billable == billable]

    # Only one time filer type is allowed
    if yesterday:
        records = [
            record
            for record in records
            if record.start
            and record.end
            and datetime.fromisoformat(record.start).date()
            == datetime.today().date() - timedelta(1)
        ]
    elif today:
        records = [
            record
            for record in records
            if record.start
            and datetime.fromisoformat(record.start).date() == datetime.today().date()
        ]
    elif week:
        records = [
            record
            for record in records
            if record.start
            and same_week(
                datetime.fromisoformat(record.start).date().strftime("%Y%m%d"),
            )
        ]
    elif month:
        records = [
            record
            for record in records
            if record.start
            and datetime.fromisoformat(record.start).month == actual_month
            and datetime.fromisoformat(record.start).year == actual_year
        ]
    elif start is not None and end is None:
        records = [
            record
            for record in records
            if record.start != ""
            and datetime.fromisoformat(record.start).date() == start.date()
        ]
    elif start is None and end is not None:
        records = [
            record
            for record in records
            if record.end != ""
            and datetime.fromisoformat(record.end).date() == end.date()
        ]
    elif start is not None and end is not None:
        records = [
            record
            for record in records
            if record.end != ""
            and record.start != ""
            and datetime.fromisoformat(record.start).date() >= start.date()
            and datetime.fromisoformat(record.end).date() <= end.date()
        ]

    return records
