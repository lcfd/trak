"""`trak --json` alone: what the menu screen shows, as data."""

from sqlalchemy import Engine
from sqlmodel import Session as DBSession

from trak import config, output
from trak.goals.display import goal_json
from trak.goals.services import upcoming_goals
from trak.sessions.display import session_json
from trak.sessions.services import get_active_sessions


def emit_overview(engine: Engine, dev_mode: bool) -> None:
    """The version, the running sessions and the upcoming goals."""

    with DBSession(engine) as db:
        output.emit(
            {
                "version": config.VERSION,
                "dev_mode": dev_mode,
                "active_sessions": [
                    session_json(db, s) for s in get_active_sessions(db)
                ],
                "goals": [goal_json(db, g) for g in upcoming_goals(db)],
            }
        )
