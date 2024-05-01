from rich import print as rprint
from rich.panel import Panel

from trakcli.utils.print_with_padding import print_with_padding


def print_info(title: str, text: str):
    shown_title = title if title else "Info"
    shown_text = text if text else ("Info text")
    rprint("")
    rprint(
        Panel.fit(
            title=f"[bold royal_blue1]{ shown_title }[/bold royal_blue1]",
            renderable=print_with_padding(shown_text),
        )
    )
