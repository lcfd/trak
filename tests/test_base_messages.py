import pytest

from trak import base_messages
from trak.base_messages import (
    PANEL_MIN_WIDTH,
    print_error,
    print_info,
    print_success,
    print_warning,
)


def box_widths(output: str) -> set[int]:
    return {
        len(line) for line in output.splitlines() if line.startswith(("╭", "│", "╰"))
    }


@pytest.mark.parametrize(
    "printer", [print_error, print_info, print_success, print_warning]
)
def test_short_messages_get_the_minimum_width(capsys, printer):
    printer(title="Hi", text="Short.")

    assert box_widths(capsys.readouterr().out) == {PANEL_MIN_WIDTH}


def test_long_messages_grow_past_the_minimum(capsys):
    text = "x" * (PANEL_MIN_WIDTH + 5)

    print_info(title="Long", text=text)

    [width] = box_widths(capsys.readouterr().out)
    assert width > PANEL_MIN_WIDTH


def test_boxes_never_exceed_the_terminal(capsys, monkeypatch):
    monkeypatch.setattr(base_messages, "PANEL_MIN_WIDTH", 500)

    print_info(title="Wide", text="Short.")

    [width] = box_widths(capsys.readouterr().out)
    assert width <= 120
