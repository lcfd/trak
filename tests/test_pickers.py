"""The calendar (and time) picker of date fields: keys, answers, typing."""

from datetime import date, datetime

import pytest

from tests.fakes import FakeScreen
from trak.pickers import DatePicker, add_months, parse_moment
from trak.prompts import PromptCancelled, ScreenPrompter
from trak.sessions.guided import input_validator

NOW = datetime(2026, 10, 21, 14, 32)
TAB = "\t"


def picker(value="", **kwargs) -> DatePicker:
    return DatePicker("Start", value=value, now=NOW, **kwargs)


def press(element, *keys):
    for key in keys:
        element.handle_key(key)
    return element


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-10-02 08:15", datetime(2026, 10, 2, 8, 15)),
        ("09:30", datetime(2026, 10, 21, 9, 30)),
        ("now", NOW),
        ("2026-12-25", datetime(2026, 12, 25, 14, 32)),
        ("tomorrow", datetime(2026, 10, 22, 14, 32)),
        ("+3", datetime(2026, 10, 24, 14, 32)),
        ("", None),
        ("1h30m", None),
    ],
)
def test_parse_moment(text, expected):
    assert parse_moment(text, NOW) == expected


def test_add_months_keeps_the_day_within_the_month():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 3, 10), -12) == date(2025, 3, 10)


def test_it_starts_on_the_value():
    assert picker("2026-10-02").value == "2026-10-02"
    assert picker("2026-10-02 08:15", with_time=True).value == "2026-10-02 08:15"


def test_vim_keys_move_the_day():
    p = picker("2026-10-21")

    assert press(p, "l").value == "2026-10-22"
    assert press(p, "h", "h").value == "2026-10-20"
    assert press(p, "j").value == "2026-10-27"
    assert press(p, "k", "k").value == "2026-10-13"
    assert press(p, "]").value == "2026-11-13"
    assert press(p, "[", "[").value == "2026-09-13"
    assert press(p, "}").value == "2027-09-13"
    assert press(p, "g").value == "2027-09-01"
    assert press(p, "G").value == "2027-09-30"
    assert press(p, "t").value == "2026-10-21"


def test_tab_goes_to_the_time_where_digits_type_it():
    p = picker("2026-10-21 09:00", with_time=True)

    press(p, TAB, "1", "7", "4", "5")

    assert p.value == "2026-10-21 17:45"


def test_j_k_change_the_hour_and_the_minute_by_steps():
    p = picker("2026-10-21 09:32", with_time=True)

    assert press(p, TAB, "k").value == "2026-10-21 10:32"
    # The minute goes to the next multiple of 5, then by 5.
    assert press(p, "l", "j").value == "2026-10-21 10:30"
    assert press(p, "j").value == "2026-10-21 10:25"
    assert press(p, "k", "k").value == "2026-10-21 10:35"
    # h goes back to the hour, then the day.
    assert press(p, "h", "h", "l").value == "2026-10-22 10:35"


def test_n_is_now():
    assert press(picker("2026-01-01 08:00", with_time=True), "n").value == (
        "2026-10-21 14:32"
    )


def test_empty_means_something_until_a_day_is_picked():
    p = picker(empty="none")

    assert p.value == "" and p.answer == "none"
    assert press(p, "l").value == "2026-10-22"
    assert press(p, "x").value == ""


def test_x_does_nothing_when_an_answer_is_needed():
    p = picker()

    assert p.value == "2026-10-21"
    assert press(p, "x").value == "2026-10-21"


def test_i_types_it_and_esc_goes_back_to_the_calendar():
    p = picker("2026-10-21")

    press(p, "i", "\x15", *"+2")
    assert p.value == "+2"
    press(p, "\x1b")
    assert p.typing is None and p.value == "2026-10-21"


def test_a_value_the_calendar_cant_show_stays_typed():
    p = picker("1h30m", with_time=True, empty="now")

    assert p.typing is not None and p.value == "1h30m"


def test_enter_checks_the_answer():
    def no_weekends(text: str) -> None:
        if date.fromisoformat(text).weekday() >= 5:
            raise ValueError("not on a weekend")

    p = picker("2026-10-23", validator=input_validator(no_weekends))

    assert p.handle_key("\r") is True
    press(p, "l")
    assert p.handle_key("\r") is False
    assert p.error == "Not on a weekend"


def test_esc_goes_back():
    with pytest.raises(PromptCancelled):
        picker().handle_key("\x1b")


def test_the_prompter_answers_text_from_the_calendar():
    screen = FakeScreen(["l", "\r"], 120, 30)
    prompter = ScreenPrompter(title="projects create")
    prompter.screen = screen

    answer = prompter.input("End", value="2026-10-21", picker="date", empty="none")

    assert answer == "2026-10-22"
    assert "October 2026" in screen.frames[0]
    assert "Mo Tu We Th Fr Sa Su" in screen.frames[0]
    assert prompter.answers == [("End", "2026-10-22")]
