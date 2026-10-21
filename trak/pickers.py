"""
A calendar to pick a day, and a time with it: what keys do to it (no
drawing; `ScreenPrompter.input(..., picker=...)` asks with it).

    ‹ October 2026 ›
    Mo Tu We Th Fr Sa Su
              1  2  3  4
     5  6  7  8  9 10 11
    ...
    Time  14:30

On the day: h/l a day, j/k a week, [/] a month, {/} a year, t today. With a
time, Tab goes to the hour and the minute: j/k change them, digits type them
(two each), n is now. `x` empties it when empty means something ("none",
"running"). `i` types it instead, in the formats the flags take; Esc there
goes back to the calendar. Enter picks, Esc goes back.

The answer is text, as if typed (`YYYY-MM-DD`, `YYYY-MM-DD HH:MM`, or empty),
so callers parse and check it as they do typed answers.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Literal

from rich.text import Text

from trak.dates import parse_date
from trak.prompts import (
    BACKSPACE,
    DOWN,
    ENTER,
    ESC,
    LEFT,
    RIGHT,
    UP,
    PromptCancelled,
    TextInput,
    Validator,
)

BACKTAB = "\x1b[Z"
TAB = "\t"
# The minutes j/k move by.
MINUTE_STEP = 5

Part = Literal["day", "hour", "minute"]


def parse_moment(text: str, now: datetime) -> datetime | None:
    """
    What a typed answer starts the calendar on (local, naive): "YYYY-MM-DD
    HH:MM", "HH:MM" (today), "now", or a day as `parse_date` takes it. None
    when it's empty or none of these.
    """

    text = text.strip()
    if not text:
        return None
    if text.lower() == "now":
        return now
    for fmt in ("%Y-%m-%d %H:%M", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            return now.replace(hour=parsed.hour, minute=parsed.minute)
        return parsed
    try:
        day = parse_date(text, on=now.date())
    except ValueError:
        return None
    return datetime.combine(day, now.time())


def add_months(day: date, months: int) -> date:
    """The same day `months` later (or earlier), kept within its month."""

    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return day.replace(year=year, month=month + 1, day=min(day.day, last))


class DatePicker:
    """A day on a calendar (and a time, `with_time`): what keys do to it."""

    def __init__(
        self,
        label: str,
        *,
        value: str = "",
        with_time: bool = False,
        empty: str | None = None,
        placeholder: str = "",
        validator: Validator | None = None,
        now: datetime | None = None,
    ) -> None:
        self.label = label
        self.with_time = with_time
        # What an empty answer means ("now", "none"); None: it needs one.
        self.empty = empty
        self.placeholder = placeholder
        self.validator = validator
        self.now = (now or datetime.now()).astimezone().replace(tzinfo=None)
        self.today = self.now.date()

        start = parse_moment(value, self.now)
        moment = (start or self.now).replace(second=0, microsecond=0)
        self.day = moment.date()
        self.hour, self.minute = moment.hour, moment.minute
        # Nothing picked yet: the answer is empty, which means `empty`.
        self.unset = start is None and empty is not None
        self.part: Part = "day"
        # Digits typed into the hour or minute, until there are two.
        self.digits = ""
        self.error = ""
        # Typing the answer instead (`i`); the calendar's answer otherwise.
        self.typing: TextInput | None = None
        if value.strip() and start is None:
            # Something the calendar can't show, like a duration: keep it typed.
            self.type_it(value)

    # The answer.

    @property
    def value(self) -> str:
        if self.typing is not None:
            return self.typing.value
        if self.unset:
            return ""
        if self.with_time:
            return f"{self.day.isoformat()} {self.hour:02d}:{self.minute:02d}"
        return self.day.isoformat()

    @property
    def answer(self) -> str:
        return self.value or self.empty or ""

    def validate(self) -> bool:
        if self.validator is None:
            return True
        from pydantic import ValidationError

        try:
            self.validator.validate_python(self.value.strip())
        except ValidationError as e:
            self.error = e.errors()[0].get("msg", "Not valid")
            return False
        return True

    # Keys.

    def type_it(self, text: str) -> None:
        self.typing = TextInput(
            self.label,
            value=text,
            placeholder=self.placeholder,
            validator=self.validator,
        )

    def set_day(self, day: date) -> None:
        self.day = day
        self.unset = False

    def handle_key(self, key: str) -> bool:
        """Act on `key`; True when it picked a valid answer."""

        if self.typing is not None:
            if key == ESC:
                # Back to the calendar, as it was.
                self.typing = None
                return False
            return self.typing.handle_key(key)

        if key in ENTER:
            self.digits = ""
            return self.validate()
        self.error = ""
        if key in (ESC, "q"):
            raise PromptCancelled
        if key == "i":
            self.type_it(self.value)
        elif key == "x" and self.empty is not None:
            self.unset = True
        elif key == "t":
            self.set_day(self.today)
        elif key == "n" and self.with_time:
            self.set_day(self.now.date())
            self.hour, self.minute = self.now.hour, self.now.minute
        elif key in (TAB, BACKTAB) and self.with_time:
            parts: list[Part] = ["day", "hour", "minute"]
            step = 1 if key == TAB else -1
            self.part = parts[(parts.index(self.part) + step) % len(parts)]
            self.digits = ""
        elif self.part == "day":
            self.day_key(key)
        else:
            self.time_key(key)
        return False

    def day_key(self, key: str) -> None:
        moves = {"h": -1, "l": 1, "j": 7, "k": -7}
        moves.update({LEFT: -1, RIGHT: 1, DOWN: 7, UP: -7})
        if key in moves:
            self.set_day(self.day + timedelta(days=moves[key]))
        elif key in ("[", "]"):
            self.set_day(add_months(self.day, 1 if key == "]" else -1))
        elif key in ("{", "}"):
            self.set_day(add_months(self.day, 12 if key == "}" else -12))
        elif key == "g":
            self.set_day(self.day.replace(day=1))
        elif key == "G":
            last = calendar.monthrange(self.day.year, self.day.month)[1]
            self.set_day(self.day.replace(day=last))

    def time_key(self, key: str) -> None:
        if key in ("h", LEFT):
            self.part = "day" if self.part == "hour" else "hour"
            self.digits = ""
            return
        if key in ("l", RIGHT):
            self.part = "minute"
            self.digits = ""
            return
        if key in BACKSPACE:
            self.digits = self.digits[:-1]
            return
        if key.isdigit() and len(key) == 1:
            self.digits += key
            if len(self.digits) == 2:
                number = int(self.digits)
                self.digits = ""
                if self.part == "hour":
                    self.hour = min(number, 23)
                    self.part = "minute"
                else:
                    self.minute = min(number, 59)
                self.unset = False
            return
        step = {"k": 1, UP: 1, "j": -1, DOWN: -1}.get(key)
        if step is None:
            return
        self.unset = False
        if self.part == "hour":
            self.hour = (self.hour + step) % 24
        else:
            # To the next multiple of the step, then by steps.
            down = self.minute - self.minute % MINUTE_STEP
            if step > 0:
                self.minute = (down + MINUTE_STEP) % 60
            else:
                self.minute = (down - MINUTE_STEP if down == self.minute else down) % 60

    def hints(self) -> list[tuple[str, str]]:
        if self.typing is not None:
            return [("Enter", "confirm"), ("Esc", "calendar"), ("Ctrl-u", "clear")]
        if self.part == "day":
            pairs = [("h/l", "day"), ("j/k", "week"), ("[ ]", "month"), ("t", "today")]
        else:
            pairs = [("j/k", "+/-"), ("0-9", "type")]
        if self.with_time:
            pairs += [("Tab", "time" if self.part == "day" else "next"), ("n", "now")]
        if self.empty is not None:
            pairs.append(("x", self.empty))
        return [*pairs, ("i", "type it"), ("Enter", "pick"), ("Esc", "back")]

    # Drawing.

    def calendar_lines(self) -> list[Text]:
        on_day = self.part == "day" and not self.unset
        title = Text.assemble(
            ("‹ ", "dim"), (f"{self.day:%B %Y}", "bold"), (" ›", "dim")
        )
        lines = [title, Text("Mo Tu We Th Fr Sa Su", style="dim")]
        for week in calendar.Calendar().monthdatescalendar(
            self.day.year, self.day.month
        ):
            line = Text()
            for index, day in enumerate(week):
                if index:
                    line.append(" ")
                if day.month != self.day.month:
                    line.append("  ")
                    continue
                style = ""
                if day == self.day:
                    style = "bold reverse green" if on_day else "reverse"
                elif day == self.today:
                    style = "bold underline"
                line.append(f"{day.day:>2}", style=style)
            lines.append(line)
        return lines

    def time_line(self) -> Text:
        def part(name: Part, number: int) -> tuple[str, str]:
            if self.part == name and self.digits:
                return f"{self.digits:<2}", "bold reverse cyan"
            if self.part == name:
                return f"{number:02d}", "bold reverse green"
            return f"{number:02d}", "dim" if self.unset else ""

        return Text.assemble(
            ("Time  ", "dim"),
            part("hour", self.hour),
            ":",
            part("minute", self.minute),
        )

    def body(self, width: int, height: int) -> list[Text]:
        if self.typing is not None:
            lines = self.typing.body(width, height)
            if self.placeholder:
                lines.append(Text(self.placeholder, style="dim"))
            return lines

        lines = self.calendar_lines()
        if self.with_time:
            lines += [Text(), self.time_line()]
        lines.append(Text())
        if self.unset:
            answer = Text.assemble(("› ", "bold green"), (self.empty or "", "bold"))
        else:
            answer = Text.assemble(("› ", "bold green"), (self.value, "bold"))
            if self.empty is not None:
                answer.append(f"  x for {self.empty}", style="dim")
        lines.append(answer)
        if self.error:
            lines.append(Text(self.error, style="bold red"))
        return lines


def picker_of(kind: str, label: str, **kwargs: Any) -> DatePicker:
    """The picker `ScreenPrompter.input(..., picker=kind)` asks with."""

    return DatePicker(label, with_time=kind == "datetime", **kwargs)
