"""Days typed by the user, for goals and projects."""

from datetime import date, datetime, timedelta

DATE_PLACEHOLDER = 'YYYY-MM-DD, "today", "tomorrow" or "+N" (in N days)'


def today() -> date:
    return datetime.now().date()


def parse_date(value: str, on: date | None = None) -> date:
    """
    A day typed by the user: "YYYY-MM-DD", "today", "tomorrow", or "+N" for
    N days from `on` (today).
    """

    value = value.strip().lower()
    on = on or today()
    if value == "today":
        return on
    if value == "tomorrow":
        return on + timedelta(days=1)
    if value.startswith("+") and value[1:].isdigit():
        return on + timedelta(days=int(value[1:]))
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"use {DATE_PLACEHOLDER}") from None


def parse_optional_date(value: str) -> date | None:
    """Like `parse_date`, but empty means no day."""

    return parse_date(value) if value.strip() else None
