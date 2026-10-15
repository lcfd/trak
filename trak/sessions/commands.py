import sys
from collections.abc import Callable
from typing import Annotated, Any, NoReturn, TypeVar

import typer
from sqlmodel import Session as DBSession
from sqlmodel import select

from trak import output
from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.prompts import PromptCancelled
from trak.sessions.display import (
    running_text,
    session_json,
    session_label,
    started_text,
    stopped_text,
)
from trak.sessions.guided import (
    Prompter,
    SessionFields,
    ask_project_and_customer,
    ask_session_fields,
    ask_session_to_stop,
    make_prompter,
    parse_start,
)
from trak.sessions.models import Category, Session, Tag
from trak.sessions.services import get_active_sessions, start_session, stop_session

T = TypeVar("T")


def find_project(db: DBSession, name: str, archived: bool = False) -> Project | None:
    """The project called `name`, printing an error if it isn't unique."""

    projects = get_projects(db, name=name, archived=archived)

    if len(projects) == 1:
        return projects[0]

    if projects:
        print_error(
            title="Ambiguous project",
            text=f"There are {len(projects)} projects called [green]{name}[/green].",
        )
        return None

    available = get_projects(db, archived=archived)
    if available:
        names = "\n".join(f" • {project.name}" for project in available)
        text = f"Available projects are:\n\n{names}"
    else:
        text = "You don't have any project yet."
    print_error(
        title="This project doesn't exist",
        text=(
            f"{text}\n\n"
            'Run "trak create project <project name>" to create a new project.'
        ),
    )
    return None


def find_customer(db: DBSession, name: str) -> Customer | None:
    """The customer called `name`, printing an error if it isn't unique."""

    customers = get_customers(db, name=name)

    if len(customers) == 1:
        return customers[0]

    if customers:
        print_error(
            title="Ambiguous customer",
            text=f"There are {len(customers)} customers called [green]{name}[/green].",
        )
        return None

    available = [c.name for c in get_customers(db) if c.name]
    if available:
        names = "\n".join(f" • {customer}" for customer in available)
        text = f"Available customers are:\n\n{names}"
    else:
        text = "You don't have any customer yet."
    print_error(title="This customer doesn't exist", text=text)
    return None


def find_row(db: DBSession, model: Any, name: str, noun: str) -> Any | None:
    """The `model` row (a Category, a Tag) called `name`, printing an error if
    it isn't unique."""

    rows = list(db.exec(select(model).where(model.name == name)))
    if len(rows) == 1:
        return rows[0]

    if rows:
        print_error(
            title=f"Ambiguous {noun}",
            text=f"There are {len(rows)} {noun}s called [green]{name}[/green].",
        )
        return None

    available = [row.name for row in db.exec(select(model).order_by(model.name))]
    if available:
        names = "\n".join(f" • {row}" for row in available)
        text = f"Available {noun}s are:\n\n{names}"
    else:
        text = f"You don't have any {noun} yet."
    print_error(title=f"This {noun} doesn't exist", text=text)
    return None


def association_fks(
    db: DBSession,
    *,
    project: str | None = None,
    customer: str | None = None,
    category: str | None = None,
    tag: str | None = None,
) -> dict[str, int | None]:
    """
    The `*_fk` fields of a Session from the flags naming its associations.

    A flag left out (None) isn't in the result; an empty one means none.
    Exits with 1, after the error, when a name matches no row or several.
    """

    finders = {
        "project_fk": (project, lambda n: find_project(db, n, archived=True)),
        "customer_fk": (customer, lambda n: find_customer(db, n)),
        "category_fk": (category, lambda n: find_row(db, Category, n, "category")),
        "tag_fk": (tag, lambda n: find_row(db, Tag, n, "tag")),
    }
    fks: dict[str, int | None] = {}
    for field, (name, find) in finders.items():
        if name is None:
            continue
        if not name.strip():
            fks[field] = None
            continue
        row = find(name.strip())
        if row is None:
            raise typer.Exit(1)
        fks[field] = row.id
    return fks


def session_customer_fk(
    db: DBSession, project_fk: int | None, customer_fk: int | None
) -> int | None:
    """
    The Customer to store on a Session. A Project's Customer applies to its
    Sessions: they can't have another one (and don't store the same twice).
    """

    project = db.get(Project, project_fk) if project_fk is not None else None
    if project is None or project.customer_fk is None:
        return customer_fk
    if customer_fk is not None and customer_fk != project.customer_fk:
        raise ValueError(
            f'The project "{project.name}" has its own customer: '
            "its sessions can't have another one."
        )
    return None


def fail(title: str, error: ValueError) -> NoReturn:
    """Print a parsing or validation error and exit with 1."""

    message = str(error)
    print_error(title=title, text=message[:1].upper() + message[1:])
    raise typer.Exit(1)


# Options shared by the commands that set a Session's fields.

CustomerOption = Annotated[
    str | None,
    typer.Option("--customer", "-c", help="The customer, by name. Empty for none."),
]
CategoryOption = Annotated[
    str | None,
    typer.Option("--category", help="The category, by name. Empty for none."),
]
TagOption = Annotated[
    str | None,
    typer.Option("--tag", "-t", help="The tag, by name. Empty for none."),
]


def is_interactive() -> bool:
    """Prompts and browsers are allowed: a terminal, and not in JSON mode."""

    return not output.json_mode() and sys.stdin.isatty() and sys.stdout.isatty()


def run_prompts(ask: Callable[[Prompter], T], cancelled: str = "") -> T:
    """
    Run interactive prompts. Ctrl-C exits with 130; going back (Esc or q)
    prints `cancelled` and exits with 1.
    """

    try:
        with make_prompter() as prompter:
            return ask(prompter)
    except PromptCancelled:
        print_warning(title="Cancelled", text=cancelled or "Nothing was changed.")
        raise typer.Exit(1)
    except (KeyboardInterrupt, SystemExit):
        # On Ctrl-C rich-toolkit prints "Cancelled." and calls exit().
        raise typer.Exit(130)


def start(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Argument(
            metavar="PROJECT",
            help="The project to track. Leave it empty to pick one interactively.",
        ),
    ] = None,
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="A name for the session."),
    ] = "",
    customer_name: CustomerOption = None,
    category: CategoryOption = None,
    tag: TagOption = None,
    start_time: Annotated[
        str | None,
        typer.Option(
            "--start",
            "-s",
            help='When it started, if not now: "HH:MM" or "YYYY-MM-DD HH:MM".',
        ),
    ] = None,
    guided: Annotated[
        bool,
        typer.Option(
            "--guided",
            "-g",
            help="Fill in every field of the session interactively, "
            "starting from the options.",
        ),
    ] = False,
) -> None:
    """
    Start a new session, optionally on a project. Every field has an option;
    in a terminal, without a project, customer, category or tag, asks for
    the project.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)

        fks = association_fks(db, customer=customer_name, category=category, tag=tag)
        fields = SessionFields(
            name=name, project_fk=project.id if project else None, **fks
        )
        if start_time is not None:
            try:
                fields.start = parse_start(start_time)
            except ValueError as e:
                fail("Can't start the session", e)

        if guided:
            if not is_interactive():
                print_error(
                    title="Guided mode needs a terminal",
                    text="Run it in an interactive terminal, or drop -g/--guided.",
                )
                raise typer.Exit(1)

            fields = run_prompts(
                lambda prompter: ask_session_fields(
                    db, prompter, project=project, name=name, defaults=fields
                ),
                cancelled="No session was started.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No session was started.")
                raise typer.Exit(1)

        elif project is None and not fks and is_interactive():
            run_prompts(
                lambda prompter: ask_project_and_customer(db, prompter, fields),
                cancelled="No session was started.",
            )

        try:
            fields.customer_fk = session_customer_fk(
                db, fields.project_fk, fields.customer_fk
            )
        except ValueError as e:
            fail("Can't start the session", e)

        session = start_session(db, **vars(fields))

        output.emit(session_json(db, session))
        print_success(
            title="▶️  Started",
            text=started_text(db, session, running=len(get_active_sessions(db))),
        )


def stop(
    ctx: typer.Context,
    project_name: Annotated[
        str | None,
        typer.Argument(
            metavar="PROJECT",
            help="Stop only the sessions of this project.",
        ),
    ] = None,
    all_: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Stop every matching session instead of picking one.",
        ),
    ] = False,
    session_id: Annotated[
        int | None,
        typer.Option("--id", help="Stop this session, instead of picking one."),
    ] = None,
) -> None:
    """
    Stop an active session, picking it from a list if more than one is running.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        sessions = get_active_sessions(db)

        if session_id is not None:
            sessions = [s for s in sessions if s.id == session_id]
            if not sessions:
                exists = db.get(Session, session_id) is not None
                print_error(
                    title="Can't stop the session",
                    text=(
                        f"Session #{session_id} isn't running."
                        if exists
                        else f"There's no session #{session_id}."
                    ),
                )
                raise typer.Exit(1)

        if project_name is not None:
            project = find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)
            sessions = [s for s in sessions if s.project_fk == project.id]

        if not sessions:
            output.emit([])
            print_info(
                title="No active sessions",
                text=(
                    "There aren't active sessions to stop.\n\n"
                    'Use the command "trak start" to start a new session.'
                ),
            )
            return

        if len(sessions) > 1 and not all_:
            if is_interactive():
                candidates = sessions
                sessions = [
                    run_prompts(
                        lambda prompter: ask_session_to_stop(db, prompter, candidates),
                        cancelled="No session was stopped.",
                    )
                ]
            else:
                active = "\n".join(
                    f" • {session_label(db, s)} since "
                    f"{s.start.astimezone():%Y-%m-%d %H:%M}"
                    for s in sessions
                )
                print_error(
                    title="Multiple active sessions",
                    text=(
                        f"{active}\n\n"
                        'Pick one with "trak stop --id ID", '
                        'or use "trak stop --all" to stop them all.'
                    ),
                )
                raise typer.Exit(1)

        stopped = [stop_session(db, session) for session in sessions]

        output.emit([session_json(db, session) for session in stopped])
        print_success(
            title="⏹️  Stopped",
            text=stopped_text(db, stopped, running=len(get_active_sessions(db))),
        )


def status(ctx: typer.Context) -> None:
    """
    Show the running sessions: what they are and how long they've been going.
    With --json, a list of sessions (empty when nothing is running).
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        sessions = get_active_sessions(db)
        output.emit([session_json(db, session) for session in sessions])

        if not sessions:
            print_info(
                title="No active sessions",
                text='Nothing is running. Start a session with "trak start".',
            )
            return

        print_info(
            title=f"⏱️  Running ({len(sessions)})", text=running_text(db, sessions)
        )
