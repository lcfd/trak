"""
Copy text to the system clipboard, for `y` in full-screen views.

`y` copies what's selected: the id of the row under the cursor, or of what
the view shows when nothing is (see `copied`).

The first clipboard tool found that works (pbcopy, wl-copy, xclip, xsel,
clip.exe); without one (e.g. over ssh), the OSC 52 escape sequence asks the
terminal itself to copy it, which most modern terminals do.
"""

import base64
import shutil
import subprocess

from rich.console import Console
from rich.markup import escape

TOOLS = [
    ["pbcopy"],
    ["wl-copy"],
    ["xclip", "-selection", "clipboard"],
    ["xsel", "--clipboard", "--input"],
    ["clip.exe"],
]


def copy(text: str, console: Console | None = None) -> bool:
    """Copy `text`; False if nothing could (no tool, and not a terminal)."""

    for tool in TOOLS:
        if shutil.which(tool[0]) is None:
            continue
        try:
            subprocess.run(
                tool, input=text.encode(), check=True, capture_output=True, timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            continue
        return True

    if console is not None and console.is_terminal:
        encoded = base64.b64encode(text.encode()).decode()
        console.file.write(f"\x1b]52;c;{encoded}\a")
        console.file.flush()
        return True
    return False


def copied(text: str, console: Console | None = None, what: str = "") -> str:
    """
    Copy `text`, and say how it went: the footer message of a view.
    `what` says what it is ("session", "command"): "Copied 12 · session".
    """

    if copy(text, console):
        about = f" [dim]· {escape(what)}[/dim]" if what else ""
        return f"[green]Copied[/green] [bold]{escape(text)}[/bold]{about}"
    return "[yellow]No clipboard to copy to.[/yellow]"
