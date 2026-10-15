"""
Edit forms: a menu of fields with their values, plus Save.

Picking a field asks for its new value; changed fields get a "•". Esc on the
field list discards everything (PromptCancelled), Esc on a field keeps it.
"""

from collections.abc import Callable
from typing import Any

from rich_toolkit.menu import Option

from trak.prompts import PromptCancelled
from trak.sessions.guided import Prompter

SAVE = "save"

# (field, label, value as text) for each row of the form.
Row = tuple[str, str, str]


def current(original: Any, changes: dict[str, Any], field: str) -> Any:
    return changes.get(field, getattr(original, field))


def effective_changes(original: Any, changes: dict[str, Any]) -> dict[str, Any]:
    return {
        field: value
        for field, value in changes.items()
        if getattr(original, field) != value
    }


def ask_changes(
    prompter: Prompter,
    title: str,
    original: Any,
    rows: Callable[[dict[str, Any]], list[Row]],
    ask_field: Callable[[dict[str, Any], str], None],
) -> dict[str, Any]:
    """
    Let the user change fields until they pick Save; returns what changed.

    `rows(changes)` lists the fields as they are now; `ask_field(changes,
    field)` asks for a new value and records it in `changes`.
    """

    changes: dict[str, Any] = {}
    last = None

    while True:
        changed = effective_changes(original, changes)
        shown = rows(changes)
        width = max(len(label) for _, label, _ in shown)
        options: list[Option[str]] = [
            {
                "name": f"{label:<{width}}  {text}"
                + ("  •" if field in changed else ""),
                "value": field,
            }
            for field, label, text in shown
        ]
        options.append({"name": "Save", "value": SAVE})

        choice = prompter.ask(
            f"{title} · Esc to discard", options, default=last, button=SAVE
        )
        if choice == SAVE:
            return changed

        last = choice
        try:
            ask_field(changes, choice)
        except PromptCancelled:
            pass


def ask_yes_no(prompter: Prompter, label: str, value: bool) -> bool:
    options: list[Option[bool]] = [
        {"name": "Yes", "value": True},
        {"name": "No", "value": False},
    ]
    return prompter.ask(label, options, inline=True, default=value)
