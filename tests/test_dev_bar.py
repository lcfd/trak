from io import StringIO
from pathlib import Path

from rich.console import Console

from trak import dev_bar


def make_console() -> Console:
    return Console(file=StringIO(), width=40, force_terminal=True)


def test_no_bar_outside_dev_mode():
    console = make_console()

    dev_bar.print_bar(console)

    assert console.file.getvalue() == ""
    assert dev_bar.lines() == 0


def test_bar_fills_the_width(monkeypatch):
    monkeypatch.setattr(dev_bar, "dev_db_path", Path("/data/dev_db.sqlite3"))

    text = dev_bar.bar(40)

    assert text.plain.startswith(" DEV MODE · /data/dev_db.sqlite3")
    assert len(text.plain) == 40
    assert dev_bar.bar(10).cell_len == 10
    assert dev_bar.lines() == 1


def test_clear_keeps_the_bar_on_top(monkeypatch):
    monkeypatch.setattr(dev_bar, "dev_db_path", Path("/data/dev_db.sqlite3"))
    console = make_console()

    dev_bar.clear(console)

    output = console.file.getvalue()
    assert output.index("\x1b[2J") < output.index("DEV MODE")
