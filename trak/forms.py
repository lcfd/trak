"""
Edit forms: a menu of fields with their values, plus Save.

Picking a field asks for its new value; changed fields get a "•". Esc on the
field list discards everything (PromptCancelled), Esc on a field keeps it.
On screen the fields are pane [1], like the home's panes; [2] previews the
field at the cursor (its value, what it was) or, on Save, what changes.
"""

from collections.abc import Callable
from typing import Any

from rich.text import Text
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
    before = {field: (label, text) for field, label, text in rows({})}

    while True:
        changed = effective_changes(original, changes)
        shown = rows(changes)
        width = max(len(label) for _, label, _ in shown)
        now = {field: (label, text) for field, label, text in shown}
        options: list[Option[str]] = [
            {
                "name": f"{label:<{width}}  {text}"
                + ("  •" if field in changed else ""),
                "value": field,
            }
            for field, label, text in shown
        ]
        options.append({"name": "Save", "value": SAVE})

        def render(
            option: Option[Any],
            width: int = width,
            now: dict[str, tuple[str, str]] = now,
            changed: dict[str, Any] = changed,
        ) -> Text:
            label, text = now[option["value"]]
            line = Text.assemble((f"{label:<{width}}  ", "dim"), text)
            if option["value"] in changed:
                line.append("  •", style="bold yellow")
            return line

        def preview(
            field: Any,
            now: dict[str, tuple[str, str]] = now,
            changed: dict[str, Any] = changed,
        ) -> Preview:
            return preview_of(field, before, now, changed)

        choice = prompter.ask(
            title,
            options,
            default=last,
            button=SAVE,
            render=render,
            preview=preview,
        )
        if choice == SAVE:
            return changed

        last = choice
        try:
            ask_field(changes, choice)
        except PromptCancelled:
            pass


Preview = tuple[str, list[Text]]


def preview_of(
    field: str,
    before: dict[str, tuple[str, str]],
    now: dict[str, tuple[str, str]],
    changed: dict[str, Any],
) -> Preview:
    """[2] of a form: the field at the cursor, or on Save what changes."""

    if field == SAVE:
        lines: list[Text] = []
        changed_rows = [f for f in now if f in changed]
        if not changed_rows:
            return "Save", [Text("Nothing changed yet.", style="dim")]
        width = max(len(now[f][0]) for f in changed_rows)
        for f in changed_rows:
            label, text = now[f]
            was = before.get(f, (label, "—"))[1]
            lines.append(
                Text.assemble(
                    (f"{label:<{width}}  ", "dim"), (was, "dim"), " → ", (text, "bold")
                )
            )
        count = len(changed_rows)
        lines += [Text(), Text(f"Enter saves {count} change{'s' * (count > 1)}.")]
        return "Save", lines

    label, text = now[field]
    lines = [Text(text, style="bold")]
    if field in changed:
        lines.append(Text(f"was {before.get(field, (label, '—'))[1]}", style="dim"))
    lines += [Text(), Text("Enter changes it.", style="dim")]
    return label, lines


def ask_yes_no(prompter: Prompter, label: str, value: bool) -> bool:
    options: list[Option[bool]] = [
        {"name": "Yes", "value": True},
        {"name": "No", "value": False},
    ]
    return prompter.ask(label, options, inline=True, default=value)
