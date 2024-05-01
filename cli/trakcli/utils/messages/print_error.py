from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_error(title: str | None = None, text: str | None = None):
    shown_title = title if title else "Something went wrong"
    shown_text = (
        text
        if text
        else (
            "You may need to check your database.\n\n"
            "It's possible that the command has a bug.\n"
            'Please, report it on GitHub issues, "trak --bug".'
        )
    )
    rprint("")
    rprint(
        Panel.fit(
            title=f"[bold red]{ shown_title }[/bold red]",
            renderable=print_with_padding(shown_text),
        )
    )
