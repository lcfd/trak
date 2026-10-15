"""
Machine-readable output: `--json` on every command, for scripts and editors.

In JSON mode a command prints exactly one JSON document on stdout, on one
line, and nothing else: no panels, no prompts, no browsers, no dev bar.
Errors are `{"error": {"title": ..., "message": ...}}` on stderr, with
exit code 1 (usage errors from Click stay plain text, with exit code 2).

Values: datetimes are ISO 8601 in local time with the offset, dates are
`YYYY-MM-DD`, durations are whole seconds in `*_seconds` keys.
"""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import typer
from rich.text import Text
from sqlmodel import SQLModel
from typer.core import TyperGroup, TyperOption

_json_mode = False


def json_mode() -> bool:
    return _json_mode


def set_json_mode(on: bool) -> None:
    global _json_mode
    _json_mode = on


def encode(value: Any) -> Any:
    """`json.dumps` default: the values JSON doesn't know."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone().isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, SQLModel):
        return fields(value)
    raise TypeError(f"Can't encode {type(value).__name__} as JSON")


def dumps(data: Any) -> str:
    return json.dumps(data, default=encode, ensure_ascii=False)


def emit(data: Any) -> None:
    """Print `data` as the command's JSON result; nothing outside JSON mode."""

    if _json_mode:
        typer.echo(dumps(data))


def plain(markup: str) -> str:
    """Rich markup as plain text."""

    return Text.from_markup(markup).plain


def emit_error(title: str, message: str) -> None:
    typer.echo(
        dumps({"error": {"title": plain(title), "message": plain(message)}}),
        err=True,
    )


def fields(row: SQLModel) -> dict[str, Any]:
    """Every field of a model row, in the model's order."""

    return {name: getattr(row, name) for name in type(row).model_fields}


def seconds(duration: timedelta) -> int:
    return int(duration.total_seconds())


# The --json option, added to every command and group by `add_json_option`.

JSON_HELP = "Print the result as JSON, for scripts and editors. Never asks anything."


def _enable(ctx: typer.Context, param: typer.CallbackParam, value: bool) -> None:
    if value:
        set_json_mode(True)


def json_option() -> TyperOption:
    # Typer's own Click classes: Typer vendors Click, and the `click` package's
    # Option doesn't work in Typer's contexts.
    return TyperOption(
        param_decls=["--json"],
        is_flag=True,
        expose_value=False,
        is_eager=True,
        callback=_enable,
        help=JSON_HELP,
    )


def add_json_option(command: typer.core.TyperCommand | TyperGroup) -> None:
    """Give `command`, and every command under it, the --json option."""

    if not any(param.name == "json" for param in command.params):
        command.params.append(json_option())
    if isinstance(command, TyperGroup):
        for sub in command.commands.values():
            add_json_option(sub)
