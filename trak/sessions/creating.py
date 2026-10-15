"""`trak sessions create`: add a past session, for time tracked without `trak start`."""

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import typer
from sqlmodel import Session as DBSession

from trak import entities
from trak.base_messages import print_error, print_success, print_warning
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.display import created_text
from trak.sessions.editing import parse_time
from trak.sessions.guided import (
    Prompter,
    SessionFields,
    ask_name_and_associations,
    input_validator,
)
from trak.sessions.services import create_session

START_PLACEHOLDER = '"HH:MM" (today) or "YYYY-MM-DD HH:MM"'
END_PLACEHOLDER = 'now, "HH:MM", "YYYY-MM-DD HH:MM" or a duration like 1h30m'

DURATION = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)m)?")


def parse_duration(value: str) -> timedelta | None:
    """ "1h30m", "2h", "45m"; None if it isn't a duration."""

    match = DURATION.fullmatch(value.strip().lower())
    if not match or not any(match.groups()):
        return None
    hours, minutes = (int(group or 0) for group in match.groups())
    return timedelta(hours=hours, minutes=minutes)


def parse_past_start(value: str, now: datetime | None = None) -> datetime:
    """The start of a past session: it can't be empty (that would be now)."""

    if not value.strip():
        raise ValueError("a past session needs a start")
    return parse_time(value, "start", now=now)


def parse_end(value: str, start: datetime, now: datetime | None = None) -> datetime:
    """An end time, or a duration from `start`; empty means now."""

    now = now or datetime.now(UTC)
    duration = parse_duration(value)
    if duration is None:
        return parse_time(value, "end", after=start, now=now)
    if not duration:
        raise ValueError("a session needs to last at least a minute")
    end = start + duration
    if end > now:
        raise ValueError("a session can't end in the future")
    return end


def ask_new_session(
    db: DBSession, prompter: Prompter, project: Project | None = None
) -> dict[str, Any] | None:
    """Ask for every field of a past Session. None means the user gave up."""

    fields = SessionFields()
    ask_name_and_associations(db, prompter, fields, project=project)

    start = parse_past_start(
        prompter.input(
            "Start",
            placeholder=START_PLACEHOLDER,
            validator=input_validator(parse_past_start),
        )
    )
    end = parse_end(
        prompter.input(
            "End",
            placeholder=END_PLACEHOLDER,
            validator=input_validator(lambda text: parse_end(text, start)),
        ),
        start,
    )

    if not prompter.confirm("Create this session?"):
        return None
    return {**vars(fields), "start": start, "end": end}


def create_command(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Argument(
            metavar="PROJECT",
            help="The project of the session. Leave it and --start empty "
            "to fill in every field.",
        ),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option(
            "--start", "-s", help='When it started: "HH:MM" or "YYYY-MM-DD HH:MM".'
        ),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            "-e",
            help='When it ended ("HH:MM", "YYYY-MM-DD HH:MM") or how long it '
            "lasted (1h30m). Default: now.",
        ),
    ] = None,
    name: Annotated[
        str, typer.Option("--name", "-n", help="A name for the session.")
    ] = "",
    customer_name: Annotated[
        str | None,
        typer.Option("--customer", "-c", help="The customer of the session."),
    ] = None,
) -> None:
    """
    Add a past session, for time you didn't track with "trak start".
    Without a project or --start, asks for every field.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = commands.find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)

        if start is None and project is None and customer_name is None:
            entities.require_terminal("Creating a session without --start")
            fields = commands.run_prompts(
                lambda prompter: ask_new_session(db, prompter),
                cancelled="No session was created.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No session was created.")
                raise typer.Exit(1)
        else:
            if start is None:
                print_error(
                    title="When did it start?",
                    text='Give its start with --start, e.g. --start "09:30".',
                )
                raise typer.Exit(1)
            fields = {"name": name, "project_fk": project.id if project else None}
            if customer_name is not None:
                customer = commands.find_customer(db, customer_name)
                if customer is None:
                    raise typer.Exit(1)
                fields["customer_fk"] = customer.id
            try:
                fields["start"] = parse_past_start(start)
                fields["end"] = parse_end(end or "", fields["start"])
            except ValueError as e:
                message = str(e)
                print_error(
                    title="Can't create the session",
                    text=message[:1].upper() + message[1:] + ".",
                )
                raise typer.Exit(1)

        try:
            session = create_session(db, **fields)
        except ValueError as e:
            print_error(title="Can't create the session", text=str(e))
            raise typer.Exit(1)

        print_success(title="✨ Create", text=created_text(db, session))
