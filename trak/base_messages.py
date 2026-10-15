import typer
from rich import get_console, print
from rich.padding import Padding
from rich.panel import Panel

from trak import output

# Every message box is at least this wide, so they all feel the same.
PANEL_MIN_WIDTH = 60


def print_with_padding(text: str, x: int = 2, y: int = 2):
    return Padding(text, (y, x))


def print_panel(title: str, text: str) -> None:
    """A box as wide as its content, but never narrower than PANEL_MIN_WIDTH."""

    console = get_console()
    renderable = print_with_padding(text)
    fitted = console.measure(Panel.fit(title=title, renderable=renderable)).maximum
    # A Panel that doesn't expand shrinks to its content, ignoring `width`.
    panel = Panel(
        renderable,
        title=title,
        expand=True,
        width=min(max(PANEL_MIN_WIDTH, fitted), console.width),
    )

    print("")
    print(panel)


# NOTE: new way
success_message_example = typer.style("good", fg=typer.colors.GREEN, bold=True)
# another example, but for errors
# typer.style("bad", fg=typer.colors.WHITE, bg=typer.colors.RED)


# In JSON mode (see output.py) errors are JSON on stderr, and the other
# messages are left out: the command emits its result instead.


def print_error(title: str | None = None, text: str | None = None):
    shown_title = title if title else "Error"
    shown_text = (
        text
        if text
        else (
            "You may need to check your database.\n\n"
            "It's possible that the command has a bug.\n"
            'Please, report it on GitHub issues, "trak --bug".'
        )
    )
    if output.json_mode():
        output.emit_error(shown_title, shown_text)
        return
    print_panel(title=f"[bold red]{shown_title}[/bold red]", text=shown_text)


def print_info(title: str, text: str):
    if output.json_mode():
        return
    shown_title = title if title else "Info"
    shown_text = text if text else ("Info text")
    print_panel(
        title=f"[bold royal_blue1]{shown_title}[/bold royal_blue1]", text=shown_text
    )


def print_success(title: str | None = None, text: str | None = None):
    if output.json_mode():
        return
    shown_title = title if title else "Success"
    shown_text = text if text else ("Action performed successfully.")
    print_panel(title=f"[bold green]{shown_title}[/bold green]", text=shown_text)


def print_warning(title: str, text: str):
    if output.json_mode():
        return
    shown_title = title if title else "Warning"
    shown_text = text if text else ("Warning text")
    print_panel(title=f"[bold orange3]{shown_title}[/bold orange3]", text=shown_text)
