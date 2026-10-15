"""`trak dev`: tools for trak developers. Listed in --help, not in the menu."""

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from sqlmodel import Session as DBSession

from trak import config, dates, output
from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.db.engine import get_engine
from trak.db.migrations import migrate
from trak.dev.fill import clear, fill, has_data
from trak.main.routes import load_settings, settings_dev_mode
from trak.sessions import commands

# A top-level `development = ...` or `TRAK_DEV = ...` line of settings.toml.
DEV_KEY = re.compile(
    rf"""^\s*["']?(development|{config.DEV_ENV_VAR})["']?\s*=""", re.IGNORECASE
)

app = typer.Typer(no_args_is_help=True)


@app.command(name="fill")
def fill_command(
    years: Annotated[
        int, typer.Option(min=1, max=30, help="How many years of data, up to today.")
    ] = 6,
    seed: Annotated[
        int | None, typer.Option(help="Make the same data on the same day.")
    ] = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Delete what the dev database holds first.")
    ] = False,
) -> None:
    """Fill the dev database with years of made-up data, up to today."""

    engine = get_engine(config.DB_DEV_PATH)
    try:
        migrate(engine)
        with DBSession(engine) as db:
            if has_data(db):
                if not reset:
                    print_error(
                        title="The dev database isn't empty",
                        text=(
                            f"{config.DB_DEV_PATH} already holds data."
                            " Give --reset to replace it."
                        ),
                    )
                    raise typer.Exit(1)
                clear(db)
            filled = fill(
                db, today=dates.today(), now=datetime.now(UTC), years=years, seed=seed
            )
    finally:
        engine.dispose()

    output.emit(
        {
            "database": str(config.DB_DEV_PATH),
            "from": filled.first_day,
            "to": filled.last_day,
            "customers": filled.customers,
            "projects": filled.projects,
            "sessions": filled.sessions,
            "running": filled.running,
            "goals": filled.goals,
            "categories": filled.categories,
            "tags": filled.tags,
        }
    )
    print_success(
        title="Dev database filled",
        text=(
            f"{config.DB_DEV_PATH}\n\n"
            f"From {filled.first_day} to {filled.last_day}:"
            f" {filled.sessions} sessions ({filled.running} running),"
            f" {filled.projects} projects, {filled.customers} customers,"
            f" {filled.goals} goals, {filled.categories} categories,"
            f" {filled.tags} tags.\n\n"
            f"Use it with [green]{config.DEV_ENV_VAR}=1 trak[/green]."
        ),
    )


def write_dev_mode(path: Path, on: bool) -> None:
    """
    Set `development` in settings.toml, keeping the rest of the file: the
    first top-level dev key takes the new value, any other one goes.
    """

    text = path.read_text() if path.exists() else ""
    setting = f"development = {'true' if on else 'false'}"
    lines = text.splitlines()
    kept: list[str] = []
    written = False
    top_level = True
    for line in lines:
        if line.lstrip().startswith("["):
            top_level = False
        if top_level and DEV_KEY.match(line):
            if not written:
                kept.append(setting)
                written = True
            continue
        kept.append(line)
    if not written:
        kept.insert(0, setting)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept) + "\n")


@app.command(name="toggle")
def toggle_command(
    on: Annotated[
        bool | None,
        typer.Option(
            "--on/--off", help="Turn it on or off, instead of the other way round."
        ),
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Don't ask for confirmation.")
    ] = False,
) -> None:
    """Turn dev mode on or off in settings.toml: trak then uses the dev database."""

    current = settings_dev_mode(load_settings())
    target = not current if on is None else on
    state = "on" if target else "off"
    database = config.DB_DEV_PATH if target else config.DB_PATH
    data = {
        "development": target,
        "settings": str(config.SETTINGS_FILE_PATH),
        "database": str(database),
    }
    env = os.environ.get(config.DEV_ENV_VAR)

    if target == current:
        output.emit(data)
        print_info(title="Dev mode", text=f"Dev mode is already {state}.")
    else:
        if not yes:
            if not commands.is_interactive():
                print_error(
                    title="Toggling dev mode needs a confirmation",
                    text="Give --yes to toggle it without a terminal.",
                )
                raise typer.Exit(1)
            confirmed = commands.run_prompts(
                lambda prompter: prompter.confirm(
                    f"Turn dev mode {state}? trak will use {database}.",
                    default=False,
                ),
                cancelled="Dev mode didn't change.",
            )
            if not confirmed:
                print_warning(title="Cancelled", text="Dev mode didn't change.")
                raise typer.Exit(1)

        write_dev_mode(config.SETTINGS_FILE_PATH, target)
        output.emit(data)
        print_success(
            title="Dev mode",
            text=(
                f"Dev mode is {state}: trak uses {database}.\n\n"
                f"[dim]Saved in {config.SETTINGS_FILE_PATH}.[/dim]"
            ),
        )

    if env is not None:
        print_warning(
            title=f"{config.DEV_ENV_VAR} is set",
            text=(
                f"{config.DEV_ENV_VAR}={env} wins over settings.toml"
                " while it's set in this shell."
            ),
        )
