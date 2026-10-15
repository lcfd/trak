import sys
from collections.abc import Callable
from typing import Annotated, TypeVar

import typer
from sqlmodel import Session as DBSession

from trak.base_messages import print_error, print_info, print_success, print_warning
from trak.customers.models import Customer
from trak.customers.services import get_customers
from trak.projects.models import Project
from trak.projects.services import get_projects
from trak.prompts import PromptCancelled
from trak.sessions.display import session_label, started_text, stopped_text
from trak.sessions.guided import (
    Prompter,
    SessionFields,
    ask_project_and_customer,
    ask_session_fields,
    ask_session_to_stop,
    make_prompter,
)
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


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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
    guided: Annotated[
        bool,
        typer.Option(
            "--guided",
            "-g",
            help="Fill in every field of the session interactively.",
        ),
    ] = False,
) -> None:
    """
    Start a new session, optionally on a project.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        project = None
        if project_name is not None:
            project = find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)

        fields = SessionFields(name=name, project_fk=project.id if project else None)

        if guided:
            if not is_interactive():
                print_error(
                    title="Guided mode needs a terminal",
                    text="Run it in an interactive terminal, or drop -g/--guided.",
                )
                raise typer.Exit(1)

            fields = run_prompts(
                lambda prompter: ask_session_fields(
                    db, prompter, project=project, name=name
                ),
                cancelled="No session was started.",
            )
            if fields is None:
                print_warning(title="Cancelled", text="No session was started.")
                raise typer.Exit(1)

        elif project is None and is_interactive():
            run_prompts(
                lambda prompter: ask_project_and_customer(db, prompter, fields),
                cancelled="No session was started.",
            )

        session = start_session(db, **vars(fields))

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
) -> None:
    """
    Stop an active session, picking it from a list if more than one is running.
    """

    with DBSession(ctx.obj["DB_ENGINE"]) as db:
        sessions = get_active_sessions(db)

        if project_name is not None:
            project = find_project(db, project_name)
            if project is None:
                raise typer.Exit(1)
            sessions = [s for s in sessions if s.project_fk == project.id]

        if not sessions:
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
                        "Run it in a terminal to pick one, "
                        'or use "trak stop --all" to stop them all.'
                    ),
                )
                raise typer.Exit(1)

        stopped = [stop_session(db, session) for session in sessions]

        print_success(
            title="⏹️  Stopped",
            text=stopped_text(db, stopped, running=len(get_active_sessions(db))),
        )
