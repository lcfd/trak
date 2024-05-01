from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_warning(title: str, text: str):
    shown_title = title if title else "Warning"
    shown_text = text if text else ("Warning text")
    rprint("")
    rprint(
        Panel.fit(
            title=f"[bold orange3]{ shown_title }[/bold orange3]",
            renderable=print_with_padding(shown_text),
        )
    )
