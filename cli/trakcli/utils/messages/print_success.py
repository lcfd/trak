from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_success(title: str | None = None, text: str | None = None):
    shown_title = title if title else "Success"
    shown_text = text if text else ("Action performed successfully.")
    rprint("")
    rprint(
        Panel.fit(
            title=f"[bold green]{ shown_title }[/bold green]",
            renderable=print_with_padding(shown_text),
        )
    )
