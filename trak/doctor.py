"""`trak doctor`: check that the database is up to date and healthy."""

import typer
from sqlalchemy import Engine

from trak import config
from trak.base_messages import print_error, print_success
from trak.db.migrations import LATEST_VERSION, get_version


def find_problems(engine: Engine) -> list[str]:
    """What's wrong with the database, as sentences; empty when it's healthy."""

    problems = []

    version = get_version(engine)
    if version != LATEST_VERSION:
        problems.append(
            f"The schema is at version {version}, but trak expects {LATEST_VERSION}."
        )

    with engine.connect() as conn:
        integrity = [row[0] for row in conn.exec_driver_sql("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            problems.append("The integrity check failed: " + "; ".join(integrity))

        orphans = conn.exec_driver_sql("PRAGMA foreign_key_check").all()
        for table, rowid, parent, _ in orphans:
            problems.append(f"{table} {rowid} points to a missing {parent}.")

    return problems


def doctor_command(ctx: typer.Context) -> None:
    engine: Engine = ctx.obj["DB_ENGINE"]
    mode = " (development)" if ctx.obj["DEV_MODE"] else ""
    lines = [
        f"Database{mode}: {engine.url.database}",
        f"Schema version: {get_version(engine)} (latest: {LATEST_VERSION})",
        f"Settings: {config.SETTINGS_FILE_PATH}",
    ]

    problems = find_problems(engine)
    if problems:
        print_error(
            title="Something is wrong",
            text="\n".join([*lines, "", *(f"• {p}" for p in problems)]),
        )
        raise typer.Exit(1)

    print_success(
        title="Everything is in shape",
        text="\n".join([*lines, "", "The database is up to date and healthy."]),
    )
