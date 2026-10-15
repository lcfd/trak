"""`trak sessions edit`: change any field of a Session."""

from datetime import UTC, datetime
from typing import Annotated, Any

import typer
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import entities, forms
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.forms import current
from trak.labels.links import WithTags, with_tags
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.sessions import commands, listing
from trak.sessions.commands import CategoryOption, CustomerOption, TagsOption
from trak.sessions.display import session_json, session_label
from trak.sessions.guided import (
    Prompter,
    ask_category,
    ask_tags,
    input_validator,
    parse_start,
    pick,
)
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import update_session

TIME_PLACEHOLDER = 'now, "HH:MM" or "YYYY-MM-DD HH:MM"'


def format_time(moment: datetime) -> str:
    return f"{moment.astimezone():%Y-%m-%d %H:%M}"


def parse_time(
    value: str,
    verb: str,
    after: datetime | None = None,
    before: datetime | None = None,
    now: datetime | None = None,
) -> datetime:
    """
    A start or end time typed by the user; empty means now.

    It must come at or after `after`, and at or before `before`.
    """

    now = now or datetime.now(UTC)
    moment = parse_start(value, now=now, verb=verb) or now
    if after is not None and moment < after:
        raise ValueError("a session can't end before it starts")
    if before is not None and moment > before:
        raise ValueError("a session can't start after it ends")
    return moment


def row_name(db: DBSession, model: type, fk: int | None) -> str:
    row = db.get(model, fk) if fk is not None else None
    if row is None:
        return "—"
    return row.name or f"#{fk}"


def tag_list(db: DBSession, tag_fks: list[int]) -> str:
    names = [row_name(db, Tag, fk) for fk in tag_fks]
    return ", ".join(sorted(names)) or "—"


def label_rows(
    db: DBSession, category_fk: int | None, tag_fks: list[int]
) -> list[tuple[str, str, str]]:
    """The Category and Tags rows of a form, when there's something to pick."""

    rows = []
    if category_fk is not None or db.exec(select(Category)).first():
        rows.append(("category_fk", "Category", row_name(db, Category, category_fk)))
    if tag_fks or db.exec(select(Tag)).first():
        rows.append(("tag_fks", "Tags", tag_list(db, tag_fks)))
    return rows


def ask_label(
    db: DBSession, prompter: Prompter, changes: dict[str, Any], field: str, value: Any
) -> None:
    """Ask for the Category or the Tags of a form."""

    if field == "category_fk":
        changes["category_fk"] = ask_category(db, prompter, value)
    else:
        changes["tag_fks"] = ask_tags(db, prompter, value)


def field_rows(
    db: DBSession, session: Session, changes: dict[str, Any]
) -> list[tuple[str, str, str]]:
    """(field, label, value) for every field the user can edit right now."""

    if not isinstance(session, WithTags):
        session = with_tags(db, session)  # type: ignore[assignment]

    def value(field: str) -> Any:
        return current(session, changes, field)

    rows = [("name", "Name", value("name") or "—")]

    project = db.get(Project, value("project_fk")) if value("project_fk") else None
    if project is not None and project.customer_fk is not None:
        # A Project's Customer applies to its Sessions: no second one.
        customer = row_name(db, Customer, project.customer_fk)
        rows.append(("project_fk", "Project", f"{project.name} ({customer})"))
    else:
        rows.append(
            ("project_fk", "Project", row_name(db, Project, value("project_fk")))
        )
        rows.append(
            ("customer_fk", "Customer", row_name(db, Customer, value("customer_fk")))
        )

    rows += label_rows(db, value("category_fk"), value("tag_fks"))

    end = value("end")
    rows.append(("start", "Start", format_time(value("start"))))
    rows.append(("end", "End", format_time(end) if end else "running"))
    return rows


def ask_field(
    db: DBSession,
    prompter: Prompter,
    session: Session,
    changes: dict[str, Any],
    field: str,
) -> None:
    """Ask for a new value of `field` and record it in `changes`."""

    value = current(session, changes, field)

    if field == "name":
        changes["name"] = prompter.input(
            "Name", value=value, placeholder="empty for no name"
        ).strip()

    elif field == "project_fk":
        project_fk = pick(
            prompter, "Project", get_projects(db, archived=True), default=value
        )
        changes["project_fk"] = project_fk
        project = db.get(Project, project_fk) if project_fk else None
        if project is not None and project.customer_fk is not None:
            changes["customer_fk"] = None

    elif field == "customer_fk":
        changes["customer_fk"] = pick(
            prompter, "Customer", get_customers(db), default=value
        )

    elif field in ("category_fk", "tag_fks"):
        ask_label(db, prompter, changes, field, value)

    elif field == "start":
        end = current(session, changes, "end")
        changes["start"] = parse_time(
            prompter.input(
                "Start",
                value=format_time(value),
                placeholder=TIME_PLACEHOLDER,
                validator=input_validator(
                    lambda text: parse_time(text, "start", before=end)
                ),
            ),
            "start",
            before=end,
        )

    elif field == "end":
        start = current(session, changes, "start")
        placeholder = TIME_PLACEHOLDER
        if value is None:
            placeholder += ", stops the session"
        changes["end"] = parse_time(
            prompter.input(
                "End",
                value=format_time(value) if value else "",
                placeholder=placeholder,
                validator=input_validator(
                    lambda text: parse_time(text, "end", after=start)
                ),
            ),
            "end",
            after=start,
        )


def ask_edits(db: DBSession, prompter: Prompter, session: Session) -> dict[str, Any]:
    """
    Let the user change fields until they pick Save; returns what changed.

    Going back from the field list (Esc or q) raises PromptCancelled;
    going back from a single field keeps its value.
    """

    original: Any = with_tags(db, session)
    return forms.ask_changes(
        prompter,
        f"Edit session #{session.id}",
        original,
        rows=lambda changes: field_rows(db, original, changes),
        ask_field=lambda changes, field: ask_field(
            db, prompter, original, changes, field
        ),
    )


def flag_changes(
    db: DBSession,
    session: Session,
    *,
    name: str | None = None,
    project: str | None = None,
    customer: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """
    The changes the flags of `trak sessions edit` ask for; None means the
    flag wasn't given. Exits with 1, after the error, on a bad value.
    """

    changes: dict[str, Any] = commands.association_fks(
        db, project=project, customer=customer, category=category
    )
    tag_fks = commands.find_tags(db, tags)
    if tag_fks is not None:
        changes["tag_fks"] = tag_fks
    if name is not None:
        changes["name"] = name.strip()
    try:
        if start is not None:
            changes["start"] = parse_time(start, "start")
        if end is not None:
            changes["end"] = parse_time(end, "end")

        # Like the form: a Project with a Customer takes the Session's place.
        project_fk = changes.get("project_fk", session.project_fk)
        chosen = db.get(Project, project_fk) if project_fk is not None else None
        if chosen is not None and chosen.customer_fk is not None:
            if "customer_fk" in changes:
                changes["customer_fk"] = commands.session_customer_fk(
                    db, project_fk, changes["customer_fk"]
                )
            elif "project_fk" in changes:
                changes["customer_fk"] = None
    except ValueError as e:
        commands.fail("Can't save the session", e)
    return changes


def edit_command(
    ctx: typer.Context,
    session_id: Annotated[
        int | None,
        typer.Argument(
            metavar="ID",
            help="The session to edit. Leave it empty to pick one from the list.",
        ),
    ] = None,
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="The name. Empty for none.")
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="The project, by name. Empty for none."),
    ] = None,
    customer: CustomerOption = None,
    category: CategoryOption = None,
    tags: TagsOption = None,
    start: Annotated[
        str | None,
        typer.Option("--start", "-s", help=f"When it started: {TIME_PLACEHOLDER}."),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            "-e",
            help=f"When it ended: {TIME_PLACEHOLDER}. Stops a running session.",
        ),
    ] = None,
) -> None:
    """
    Edit a session: its name, project, customer, category, tags, start and end.
    --tag replaces the tags.
    With options, saves them right away; without, opens the form (terminal).
    """

    flags = {
        "name": name,
        "project": project,
        "customer": customer,
        "category": category,
        "tags": tags,
        "start": start,
        "end": end,
    }
    given = any(value is not None for value in flags.values())
    if not given:
        entities.require_terminal("Editing without options")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        session = listing.get_or_pick(db, session_id, "edit")

        if given:
            changes = forms.effective_changes(
                with_tags(db, session), flag_changes(db, session, **flags)
            )
        else:
            changes = commands.run_prompts(
                lambda prompter: ask_edits(db, prompter, session),
                cancelled="No changes were saved.",
            )

        entities.save_changes(
            db,
            session,
            changes,
            update=update_session,
            noun="session",
            label=lambda s: session_label(db, s),
            to_json=lambda s: session_json(db, s),
        )
