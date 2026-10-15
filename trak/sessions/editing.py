"""`trak sessions edit`: change any field of a Session."""

from datetime import UTC, datetime
from typing import Annotated, Any

import typer
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import entities, forms
from trak.base_messages import print_error, print_info, print_success
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.forms import current
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.sessions import commands, listing
from trak.sessions.display import session_label
from trak.sessions.guided import Prompter, input_validator, parse_start, pick
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


def field_rows(
    db: DBSession, session: Session, changes: dict[str, Any]
) -> list[tuple[str, str, str]]:
    """(field, label, value) for every field the user can edit right now."""

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

    for model, field in ((Category, "category_fk"), (Tag, "tag_fk")):
        if value(field) is not None or db.exec(select(model)).first():
            rows.append((field, model.__name__, row_name(db, model, value(field))))

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

    elif field in ("category_fk", "tag_fk"):
        model = Category if field == "category_fk" else Tag
        rows = list(db.exec(select(model).order_by(model.name)))
        changes[field] = pick(prompter, model.__name__, rows, default=value)

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

    return forms.ask_changes(
        prompter,
        f"Edit session #{session.id}",
        session,
        rows=lambda changes: field_rows(db, session, changes),
        ask_field=lambda changes, field: ask_field(
            db, prompter, session, changes, field
        ),
    )


def edit_command(
    ctx: typer.Context,
    session_id: Annotated[
        int | None,
        typer.Argument(
            metavar="ID",
            help="The session to edit. Leave it empty to pick one from the list.",
        ),
    ] = None,
) -> None:
    """
    Edit a session: its name, project, customer, category, tag, start and end.
    """

    entities.require_terminal("Editing")

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        session = listing.get_or_pick(db, session_id, "edit")

        changes = commands.run_prompts(
            lambda prompter: ask_edits(db, prompter, session),
            cancelled="No changes were saved.",
        )

        if not changes:
            print_info(title="Nothing changed", text=session_label(db, session))
            return

        try:
            session = update_session(db, session, **changes)
        except ValueError as e:
            print_error(title="Can't save the session", text=str(e))
            raise typer.Exit(1)

        print_success(
            title="✏️  Edit",
            text=f"Session #{session.id} {session_label(db, session)} saved.",
        )
