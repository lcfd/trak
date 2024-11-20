from typing import Annotated, Optional

import typer

from trak.database import delete_session_by_id, get_latest_session, get_session_by_id
from trak.models import Record
from trak.utils.base_messages import print_success


SessionIdOption = Annotated[
    Optional[int],
    typer.Option(
        "--id",
        help="The id of the session you want to delete.",
    ),
]
SessionLatestOption = Annotated[
    Optional[bool],
    typer.Option(
        "--latest",
        "-l",
        help="Delete the latest session, without providing an id.",
    ),
]


def delete_session(
    id: SessionIdOption = None,
    latest: SessionLatestOption = None,
):
    """Delete a session by id."""

    session: Record | None = None

    deleted = False
    if latest:
        tmp = get_latest_session()
        if tmp:
            s, i = tmp
            session = s
            deleted = delete_session_by_id(i)
    elif isinstance(id, int):
        session = get_session_by_id(id)
        if session:
            deleted = delete_session_by_id(id)

    if deleted:
        print_success(title="Deleted", text="Session successfully deleted.")
