import tomllib
from typing import Optional


from sqlmodel import create_engine
import typer

from trak.config import DB_PATH, SETTINGS_FILE_PATH

from .annotations import (
    MainBugOption,
    MainDocsOption,
    MainIssuesOption,
    MainRepositoryOption,
    MainVersionOption,
    MainWebsiteOption,
)


def main(
    ctx: typer.Context,
    version: Optional[bool] = MainVersionOption,
    website: Optional[bool] = MainWebsiteOption,
    repository: Optional[bool] = MainRepositoryOption,
    issues: Optional[bool] = MainIssuesOption,
    bug: Optional[bool] = MainBugOption,
    docs: Optional[bool] = MainDocsOption,
) -> None:
    """
    Keep a record of the time you dedicate to your projects.
    """

    # Initializes ctx.obj to a dict if it's None
    ctx.ensure_object(dict)

    # Settings

    try:
        with open(SETTINGS_FILE_PATH, "rb") as f:
            SETTINGS: dict[str, Any] = tomllib.load(f)
    except FileNotFoundError:
        print(f"Creating settings file at {SETTINGS_FILE_PATH}")

        with open(SETTINGS_FILE_PATH, "w") as f:
            f.write("")

        with open(SETTINGS_FILE_PATH, "rb") as f:
            SETTINGS = tomllib.load(f)

    ctx.obj["SETTINGS"] = SETTINGS

    # print(SETTINGS.get("DEBUG"))

    # DB connection

    sqlite_url = f"sqlite:///{DB_PATH}"
    # print(sqlite_url)

    # DB_ENGINE = create_engine(sqlite_url, echo=True)
    DB_ENGINE = create_engine(sqlite_url)
    # print(DB_ENGINE)

    # SQLModel.metadata.create_all(DB_ENGINE)

    ctx.obj["DB_ENGINE"] = DB_ENGINE

    # Exclusive executable callback
    if ctx.invoked_subcommand is None:
        pass

    # if version or website or repository or issues or bug or docs:
    #     raise typer.Exit()
