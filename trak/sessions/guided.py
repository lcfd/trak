"""Guided mode for `trak start -g`: ask every Session field interactively."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Annotated, Any, Protocol

from pydantic import AfterValidator, TypeAdapter
from pydantic_core import PydanticCustomError
from rich_toolkit.menu import Option
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak.customers.services import get_customers
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.prompts import ScreenPrompter
from trak.sessions.display import (
    describe_session,
    elapsed,
    format_duration,
    labels_text,
)
from trak.sessions.models import Category, Session, Tag


class Prompter(Protocol):
    """What prompts ask with (`ScreenPrompter`), so tests can script the answers."""

    def ask(self, label: str, options: list[Option[Any]], **kwargs: Any) -> Any: ...

    def input(self, title: str, **kwargs: Any) -> str: ...

    def confirm(self, label: str, default: bool = True) -> bool: ...

    def note(self, label: str, answer: str) -> None: ...


@dataclass
class SessionFields:
    name: str = ""
    project_fk: int | None = None
    customer_fk: int | None = None
    category_fk: int | None = None
    tag_fks: list[int] = field(default_factory=list)
    start: datetime | None = None


def parse_start(
    value: str, now: datetime | None = None, verb: str = "start"
) -> datetime | None:
    """
    Parse a start (or end) time typed by the user, in local time.

    Empty means now (None). Accepts "HH:MM" (today) and "YYYY-MM-DD HH:MM".
    `verb` names what can't happen in the future, for the error.
    """

    value = value.strip()
    if not value or value.lower() == "now":
        return None

    now = (now or datetime.now(UTC)).astimezone()

    for fmt in ("%H:%M", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            parsed = now.replace(
                hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0
            )
        else:
            parsed = parsed.replace(tzinfo=now.tzinfo)
        break
    else:
        raise ValueError('use "HH:MM" or "YYYY-MM-DD HH:MM"')

    if parsed > now:
        raise ValueError(f"a session can't {verb} in the future")

    return parsed.astimezone(UTC)


def input_validator(parse: Callable[[str], Any]) -> TypeAdapter:
    """
    An input validator that accepts what `parse` accepts.

    Inputs report pydantic ValidationErrors, and a plain ValueError would be
    shown as "Value error, ...": convert it.
    """

    def validate(value: str) -> str:
        try:
            parse(value)
        except ValueError as e:
            message = str(e)
            raise PydanticCustomError("input", message[:1].upper() + message[1:]) from e
        return value

    return TypeAdapter(Annotated[str, AfterValidator(validate)])


start_validator = input_validator(parse_start)


def make_prompter() -> ScreenPrompter:
    return ScreenPrompter()


def pick(
    prompter: Prompter, label: str, rows: list[Any], default: int | None = None
) -> int | None:
    """Pick one row by id, or None. Rows need `id` and `name`."""

    options: list[Option[int | None]] = [{"name": "None", "value": None}]
    options += [{"name": row.name or f"#{row.id}", "value": row.id} for row in rows]
    return prompter.ask(label, options, allow_filtering=True, default=default)


DONE = "done"


def pick_many(
    prompter: Prompter, label: str, rows: list[Any], selected: list[int]
) -> list[int]:
    """
    Pick any number of rows by id: Enter on a row toggles it (✓), Done (the
    first option) ends. Rows need `id` and `name`. Returns the ids, sorted.
    It opens typing a filter; after a toggle it stays in NORMAL mode (j/k).
    """

    chosen = set(selected)
    last: Any = DONE
    while True:
        options: list[Option[Any]] = [
            {"name": f"Done ({len(chosen)} picked)", "value": DONE}
        ]
        options += [
            {
                "name": (row.name or f"#{row.id}") + (" ✓" if row.id in chosen else ""),
                "value": row.id,
            }
            for row in rows
        ]
        last = prompter.ask(
            f"{label} · Enter toggles",
            options,
            allow_filtering=True,
            default=last,
            record=False,
            normal=last != DONE,
        )
        if last == DONE:
            break
        chosen ^= {last}
    names = [row.name for row in rows if row.id in chosen]
    prompter.note(label, ", ".join(names) or "—")
    return sorted(chosen)


def ask_category(db: DBSession, prompter: Prompter, default: int | None) -> int | None:
    """Pick the Category (None for none); without any, keeps `default`."""

    rows = list(db.exec(select(Category).order_by(Category.name)))
    if not rows:
        return default
    return pick(prompter, "Category", rows, default=default)


def ask_tags(db: DBSession, prompter: Prompter, selected: list[int]) -> list[int]:
    """Pick the Tags; without any, keeps `selected`."""

    rows = list(db.exec(select(Tag).order_by(Tag.name)))
    if not rows:
        return selected
    return pick_many(prompter, "Tags", rows, selected)


def ask_project_and_customer(
    db: DBSession,
    prompter: Prompter,
    fields: SessionFields,
    project: Project | None = None,
) -> None:
    """
    Ask for the Project and, if it has none, the Customer of `fields`; what
    `fields` already has (from the flags) is the default.
    """

    projects = get_projects(db)
    if projects:
        fields.project_fk = pick(
            prompter,
            "Project",
            projects,
            default=project.id if project else fields.project_fk,
        )

    chosen = db.get(Project, fields.project_fk) if fields.project_fk else None

    # A Project's Customer applies to its Sessions: don't ask for a second one.
    if chosen is None or chosen.customer_fk is None:
        customers = get_customers(db)
        if customers:
            fields.customer_fk = pick(
                prompter, "Customer", customers, default=fields.customer_fk
            )
    else:
        fields.customer_fk = None


def ask_name_and_associations(
    db: DBSession,
    prompter: Prompter,
    fields: SessionFields,
    project: Project | None = None,
    name: str = "",
) -> None:
    """
    Ask for the name, Project, Customer, Category and Tags of `fields`; what
    `fields` already has (from the flags) is the default.
    """

    fields.name = prompter.input(
        "Name", default=name or fields.name, placeholder="optional, e.g. Landing page"
    ).strip()

    ask_project_and_customer(db, prompter, fields, project=project)

    fields.category_fk = ask_category(db, prompter, fields.category_fk)
    fields.tag_fks = ask_tags(db, prompter, fields.tag_fks)


def ask_session_fields(
    db: DBSession,
    prompter: Prompter,
    project: Project | None = None,
    name: str = "",
    defaults: SessionFields | None = None,
) -> SessionFields | None:
    """
    Ask for every field of a new Session, with `defaults` (from the flags)
    already filled in. None means the user gave up.
    """

    fields = replace(defaults) if defaults else SessionFields()

    ask_name_and_associations(db, prompter, fields, project=project, name=name)

    start = fields.start
    fields.start = parse_start(
        prompter.input(
            "Start",
            default=f"{start.astimezone():%Y-%m-%d %H:%M}" if start else "",
            placeholder='now, "HH:MM" or "YYYY-MM-DD HH:MM"',
            validator=start_validator,
        )
    )

    if not prompter.confirm("Start this session?"):
        return None

    return fields


def ask_session_to_stop(
    db: DBSession, prompter: Prompter, sessions: list[Session]
) -> Session:
    options: list[Option[int]] = [
        {
            "name": "  ".join(
                part
                for part in (
                    describe_session(db, s),
                    labels_text(db, s),
                    (
                        f"(since {s.start.astimezone():%a %H:%M}, "
                        f"{format_duration(elapsed(s))})"
                    ),
                )
                if part
            ),
            "value": index,
        }
        for index, s in enumerate(sessions)
    ]
    return sessions[prompter.ask("Session to stop", options, allow_filtering=True)]
