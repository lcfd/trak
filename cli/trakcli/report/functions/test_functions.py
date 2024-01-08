from datetime import datetime
from trakcli.database.models import Record
from trakcli.report.functions.get_grouped_records import get_grouped_records
from trakcli.report.functions.get_table_title import get_table_title

record = Record(
    project="test", start=datetime.now().isoformat(), end=datetime.now().isoformat()
)

fake_records = [record._asdict() for _ in range(4)]


def test_get_grouped_records__base():
    test_projects = get_grouped_records(project="test", records=fake_records, all=False)

    assert len(test_projects["test"]) == 4


def test_get_table_title__base():
    assert get_table_title(today=True) == "Report for today"
