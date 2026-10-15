from contextlib import nullcontext

import pytest
from sqlmodel import Session as DBSession

from tests.fakes import FakePrompter
from trak import config, dev_bar, output
from trak.db.engine import get_engine
from trak.db.migrations import migrate
from trak.sessions import commands


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Never touch the real settings or databases."""

    monkeypatch.setattr(config, "SETTINGS_FILE_PATH", tmp_path / "config/settings.toml")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data/db.sqlite3")
    monkeypatch.setattr(config, "DB_DEV_PATH", tmp_path / "data/dev_db.sqlite3")
    monkeypatch.delenv(config.DEV_ENV_VAR, raising=False)
    monkeypatch.setattr(dev_bar, "dev_db_path", None)
    return tmp_path


@pytest.fixture(autouse=True)
def no_json_mode():
    """JSON mode is global: don't let one test's --json leak into the next."""

    output.set_json_mode(False)
    yield
    output.set_json_mode(False)


@pytest.fixture
def engine(tmp_path):
    engine = get_engine(tmp_path / "test.sqlite3")
    migrate(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with DBSession(engine) as db:
        yield db


@pytest.fixture
def cli_db():
    """The database the CLI uses, migrated and ready to be seeded."""

    engine = get_engine(config.DB_PATH)
    migrate(engine)
    with DBSession(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def interactive(monkeypatch):
    """Run commands as in a terminal."""

    monkeypatch.setattr(commands, "is_interactive", lambda: True)


@pytest.fixture
def answers(monkeypatch):
    """Answer the prompts of a command from a script (see FakePrompter)."""

    def use(*scripted, confirm=True):
        fake = FakePrompter(*scripted, confirm=confirm)
        monkeypatch.setattr(commands, "make_prompter", lambda: nullcontext(fake))
        return fake

    return use
