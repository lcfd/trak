from rich import print
from rich.padding import Padding
from rich.panel import Panel
import typer


def print_with_padding(text: str, x: int = 2, y: int = 2):
    return Padding(text, (y, x))


# NOTE: new way
success_message_example = typer.style("good", fg=typer.colors.GREEN, bold=True)
# another example, but for errors
# typer.style("bad", fg=typer.colors.WHITE, bg=typer.colors.RED)


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
    print("")
    print(
        Panel.fit(
            title=f"[bold red]{shown_title}[/bold red]",
            renderable=print_with_padding(shown_text),
        )
    )


def print_info(title: str, text: str):
    shown_title = title if title else "Info"
    shown_text = text if text else ("Info text")
    print("")
    print(
        Panel.fit(
            title=f"[bold royal_blue1]{shown_title}[/bold royal_blue1]",
            renderable=print_with_padding(shown_text),
        )
    )


def print_success(title: str | None = None, text: str | None = None):
    shown_title = title if title else "Success"
    shown_text = text if text else ("Action performed successfully.")
    print("")
    print(
        Panel.fit(
            title=f"[bold green]{shown_title}[/bold green]",
            renderable=print_with_padding(shown_text),
        )
    )


def print_warning(title: str, text: str):
    shown_title = title if title else "Warning"
    shown_text = text if text else ("Warning text")
    print("")
    print(
        Panel.fit(
            title=f"[bold orange3]{shown_title}[/bold orange3]",
            renderable=print_with_padding(shown_text),
        )
    )
