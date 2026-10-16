"""
`trak status --starship` without Typer, SQLModel or Rich: a prompt runs it on
every line and Starship gives it 500ms, while importing the app takes ~300ms.
Plain sqlite3, read-only; `run()` returns None whenever it can't answer (no
database yet, a schema it doesn't know...), and the app handles the command.
"""

import os
import sqlite3
import sys
import tomllib
from datetime import UTC, datetime

from trak import config

STARSHIP_ARGS = (["status", "-s"], ["status", "--starship"])
TRUTHY = {"1", "true", "yes", "on"}


def is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY


def dev_mode() -> bool:
    """Like `routes.is_dev_mode`, without creating settings.toml."""

    env = os.environ.get(config.DEV_ENV_VAR)
    if env is not None:
        return is_truthy(env)
    try:
        with open(config.SETTINGS_FILE_PATH, "rb") as f:
            settings = tomllib.load(f)
    except FileNotFoundError:
        return False
    for key in ("development", config.DEV_ENV_VAR):
        if key in settings:
            return is_truthy(settings[key])
    return False


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def starship_line(db: sqlite3.Connection, dev: bool, now: datetime) -> str:
    """The same line as `display.starship_text`."""

    rows = db.execute(
        "SELECT s.id, s.name, s.start, p.name, c.name"
        " FROM session s"
        " LEFT JOIN project p ON p.id = s.project_fk"
        " LEFT JOIN customer c ON c.id = COALESCE(s.customer_fk, p.customer_fk)"
        " WHERE s.active ORDER BY s.start"
    ).fetchall()
    if not rows:
        return ""
    session_id, name, start, project, customer = rows[-1]
    minutes = int((now - parse_utc(start)).total_seconds()) // 60
    hours, minutes = divmod(minutes, 60)
    parts = [project or name or customer or f"#{session_id}", f"{hours}h {minutes}m"]
    if len(rows) > 1:
        parts.append(f"+{len(rows) - 1}")
    if dev:
        parts.append("(dev)")
    return " ".join(parts)


def run(args: list[str]) -> str | None:
    """The line to print for `args`, or None to leave them to the app."""

    if args not in STARSHIP_ARGS:
        return None
    dev = dev_mode()
    path = config.DB_DEV_PATH if dev else config.DB_PATH
    if not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return starship_line(db, dev, datetime.now(UTC))
    except (sqlite3.Error, ValueError):
        return None
    finally:
        db.close()


def main() -> None:
    line = run(sys.argv[1:])
    if line is None:
        return
    if line:
        print(line)
    raise SystemExit(0)
