"""The green bar on top of every screen while in development mode."""

from pathlib import Path

from rich.console import Console
from rich.text import Text

STYLE = "bold black on green"

# The dev database in use, set by the main callback; None outside dev mode.
dev_db_path: Path | None = None


def lines() -> int:
    """How many lines the bar takes, for screens that fit the terminal."""

    return 1 if dev_db_path else 0


def bar(width: int) -> Text:
    text = Text(f" DEV MODE · {dev_db_path}", style=STYLE)
    text.truncate(width, overflow="ellipsis", pad=True)
    return text


def print_bar(console: Console) -> None:
    if dev_db_path:
        console.print(bar(console.width), soft_wrap=True)


def clear(console: Console) -> None:
    """Clear the screen, keeping the bar on top."""

    console.clear()
    print_bar(console)
