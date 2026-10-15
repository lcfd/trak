"""`trak dev`: tools for trak developers. Listed in --help, not in the menu."""

from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlmodel import Session as DBSession

from trak import config, dates, output
from trak.base_messages import print_error, print_success
from trak.db.engine import get_engine
from trak.db.migrations import migrate
from trak.dev.fill import clear, fill, has_data

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
