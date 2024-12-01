from datetime import datetime

from trak.utils.dates import datetime_to_string, format_datetime_readable, same_week


class Test_datetime_to_string:
    def test_string(self):
        fmt_date = datetime_to_string(dt="2024-12-01T20:15")
        assert isinstance(fmt_date, str)
        assert fmt_date == "2024-12-01T20:15"

    def test_datetime(self):
        fmt_date = datetime_to_string(dt=datetime(2024, 12, 1, 20, 15))
        assert isinstance(fmt_date, str)
        assert fmt_date == "2024-12-01T20:15"


class Test_format_datetime_readable:
    def test_string(self):
        fmt_date = format_datetime_readable(str_date="2024-12-01T20:15")
        assert isinstance(fmt_date, str)
        assert fmt_date == "2024-12-01, 20:15"


class Test_is_same_week:
    def test_same_week(self):
        is_same_week = same_week(datetime.today().strftime("%Y%m%d"))
        assert isinstance(is_same_week, bool)
        assert is_same_week

    def test_different_week(self):
        is_same_week = same_week("2023-10-10")
        assert isinstance(is_same_week, bool)
        assert not is_same_week

    def test_wrong_value_format(self):
        is_same_week = same_week("2023-10-10T20:00")
        assert isinstance(is_same_week, bool)
        assert not is_same_week
