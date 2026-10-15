import os
import tomllib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from trak import config, dev_bar
from trak.base_messages import print_error
from trak.db.engine import get_engine
from trak.db.migrations import DatabaseTooNewError, migrate

from .annotations import (
    MainBugOption,
    MainDocsOption,
    MainIssuesOption,
    MainRepositoryOption,
    MainVersionOption,
    MainWebsiteOption,
)
from .menu import run_menu

TRUTHY = {"1", "true", "yes", "on"}


def load_settings() -> dict[str, Any]:
    """Load settings.toml, creating an empty one if it doesn't exist."""

    try:
        with open(config.SETTINGS_FILE_PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        config.SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.SETTINGS_FILE_PATH.touch()
        return {}


def is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUTHY


def is_dev_mode(settings: dict[str, Any]) -> bool:
    env = os.environ.get(config.DEV_ENV_VAR)
    if env is not None:
        return is_truthy(env)
    # settings.toml takes `development = true`, or the env var's name as a key
    # (`TRAK_DEV = true`), so the same switch works in both places.
    for key in ("development", config.DEV_ENV_VAR):
        if key in settings:
            return is_truthy(settings[key])
    return False


def print_migration_notice(console: Console, applied: list[int], db_path: Path) -> None:
    """Say when the database was just created or upgraded, so it never happens silently."""

    if not applied:
        return
    if applied[0] == 1:
        console.print(
            f"[dim]Created the database at {db_path} (schema v{applied[-1]}).[/dim]",
            soft_wrap=True,
        )
    else:
        console.print(
            f"[dim]Upgraded the database from schema v{applied[0] - 1}"
            f" to v{applied[-1]}.[/dim]",
            soft_wrap=True,
        )


def main(
    ctx: typer.Context,
    version: bool | None = MainVersionOption,
    website: bool | None = MainWebsiteOption,
    repository: bool | None = MainRepositoryOption,
    issues: bool | None = MainIssuesOption,
    bug: bool | None = MainBugOption,
    docs: bool | None = MainDocsOption,
) -> None:
    """
    Keep a record of the time you dedicate to your projects.
    """

    # Initializes ctx.obj to a dict if it's None
    ctx.ensure_object(dict)

    # Settings

    SETTINGS = load_settings()
    ctx.obj["SETTINGS"] = SETTINGS

    # DB connection

    DEV_MODE = is_dev_mode(SETTINGS)
    ctx.obj["DEV_MODE"] = DEV_MODE

    dev_bar.dev_db_path = config.DB_DEV_PATH if DEV_MODE else None
    # On stderr, so piped output (like `--plain` lists) stays clean.
    dev_bar.print_bar(Console(stderr=True))

    DB_PATH = config.DB_DEV_PATH if DEV_MODE else config.DB_PATH
    DB_ENGINE = get_engine(DB_PATH)

    try:
        applied = migrate(DB_ENGINE)
    except DatabaseTooNewError as e:
        print_error(title="Database too new", text=f"{e} Please update trak.")
        raise typer.Exit(1)
    print_migration_notice(Console(stderr=True), applied, DB_PATH)

    ctx.obj["DB_ENGINE"] = DB_ENGINE

    # Exclusive executable callback
    if ctx.invoked_subcommand is None:
        run_menu(ctx)
