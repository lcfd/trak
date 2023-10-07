from trak.database import Record, add_track_field
from datetime import datetime


# def test_database_existance():
#     with open(DB_FILE_PATH, "a") as database:
#         print(database)
#     assert check_if_database_exists() is True


def test_database_insert():
    add_track_field(
        Record(
            project="cbf",
            start=datetime.now().isoformat(),
            end=datetime.now().isoformat(),
            billable=True,
            category="voli",
            tag="fix",
        )
    )
    assert True
