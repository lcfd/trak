"""`trak sessions create`: add a past session, for time tracked without `trak start`."""

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import typer
from sqlmodel import Session as DBSession

from trak import output
from trak.base_messages import print_error, print_success
from trak.projects.models import Project
from trak.sessions import commands
from trak.sessions.commands import CategoryOption, CustomerOption, TagsOption
from trak.sessions.display import created_text, session_json
from trak.sessions.editing import format_time, parse_time
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
    db: DBSession,
    prompter: Prompter,
    project: Project | None = None,
    defaults: SessionFields | None = None,
    end: str = "",
) -> dict[str, Any] | None:
    """
    Ask for every field of a past Session, with `defaults` and `end` (from the
    flags) already filled in. None means the user gave up.
    """

    fields = replace(defaults) if defaults else SessionFields()
    ask_name_and_associations(db, prompter, fields, project=project)

    start = parse_past_start(
        prompter.input(
            "Start",
            default=format_time(fields.start) if fields.start else "",
            placeholder=START_PLACEHOLDER,
            validator=input_validator(parse_past_start),
        )
    )
    end_moment = parse_end(
        prompter.input(
            "End",
            default=end,
            placeholder=END_PLACEHOLDER,
            validator=input_validator(lambda text: parse_end(text, start)),
        ),
        start,
    )

    if not prompter.confirm("Create this session?"):
        return None
    return {**vars(fields), "start": start, "end": end_moment}


def create_command(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Argument(
            metavar="PROJECT",
            help="The project of the session.",
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
    customer_name: CustomerOption = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
) -> None:
    """
    Add a past session, for time you didn't track with "trak start".
    Every field has an option; without --start, asks for every field in a
    terminal, starting from the options.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = commands.find_project(db, project_name, archived=True)
            if project is None:
                raise typer.Exit(1)

        fks = commands.association_fks(db, customer=customer_name, category=category)
        defaults = SessionFields(
            name=name,
            project_fk=project.id if project else None,
            tag_fks=commands.find_tags(db, tags) or [],
            **fks,
        )

        if start is None:
            if not commands.is_interactive():
                print_error(
                    title="When did it start?",
                    text='Give its start with --start, e.g. --start "09:30".',
                )
                raise typer.Exit(1)
            fields = commands.run_prompts(
                lambda prompter: ask_new_session(
                    db, prompter, project=project, defaults=defaults, end=end or ""
                ),
                cancelled="No session was created.",
            )
            if fields is None:
                commands.cancel("No session was created.")
        else:
            fields = vars(defaults)
            try:
                fields["start"] = parse_past_start(start)
                fields["end"] = parse_end(end or "", fields["start"])
            except ValueError as e:
                commands.fail("Can't create the session", e)

        try:
            fields["customer_fk"] = commands.session_customer_fk(
                db, fields["project_fk"], fields["customer_fk"]
            )
            session = create_session(db, **fields)
        except ValueError as e:
            commands.fail("Can't create the session", e)

        output.emit(session_json(db, session))
        print_success(title="✨ Create", text=created_text(db, session))
