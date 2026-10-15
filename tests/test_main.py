import pytest
import typer
from typer.testing import CliRunner

from trak import config, dev_bar
from trak.db import migrations
from trak.db.migrations import LATEST_VERSION, get_version
from trak.main.routes import is_dev_mode, main

runner = CliRunner()


@pytest.fixture
def app():
    """A minimal app with the real callback and a command exposing ctx.obj."""

    app = typer.Typer()
    app.callback(invoke_without_command=True)(main)

    @app.command()
    def probe(ctx: typer.Context):
        engine = ctx.obj["DB_ENGINE"]
        print(f"db={engine.url.database} dev={ctx.obj['DEV_MODE']}")
        print(f"version={get_version(engine)}")

    return app


def test_settings_file_is_created(app):
    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert config.SETTINGS_FILE_PATH.is_file()


def test_uses_production_database_and_migrates_it(app):
    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert f"db={config.DB_PATH} dev=False" in result.output
    assert f"version={LATEST_VERSION}" in result.output
    assert not config.DB_DEV_PATH.exists()


def test_env_var_enables_dev_database(app):
    result = runner.invoke(app, ["probe"], env={config.DEV_ENV_VAR: "1"})

    assert result.exit_code == 0, result.output
    assert f"db={config.DB_DEV_PATH} dev=True" in result.output
    assert not config.DB_PATH.exists()


def test_settings_enable_dev_database(app):
    config.SETTINGS_FILE_PATH.parent.mkdir(parents=True)
    config.SETTINGS_FILE_PATH.write_text("development = true\n")

    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert f"db={config.DB_DEV_PATH} dev=True" in result.output


@pytest.mark.parametrize(
    ("env", "settings", "expected"),
    [
        (None, {}, False),
        (None, {"development": True}, True),
        (None, {"development": False}, False),
        (None, {"TRAK_DEV": True}, True),
        (None, {"TRAK_DEV": "1"}, True),
        (None, {"TRAK_DEV": False}, False),
        ("0", {"TRAK_DEV": True}, False),
        ("1", {}, True),
        ("true", {}, True),
        ("0", {"development": True}, False),
        ("", {"development": True}, False),
    ],
)
def test_is_dev_mode(monkeypatch, env, settings, expected):
    if env is not None:
        monkeypatch.setenv(config.DEV_ENV_VAR, env)

    assert is_dev_mode(settings) is expected


def test_dev_mode_shows_the_bar(app):
    result = runner.invoke(app, ["probe"], env={config.DEV_ENV_VAR: "1"})

    assert result.exit_code == 0, result.output
    assert result.output.startswith(" DEV MODE · ")
    assert dev_bar.dev_db_path == config.DB_DEV_PATH


def test_production_has_no_bar(app):
    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert "DEV MODE" not in result.output
    assert dev_bar.dev_db_path is None


def test_fresh_database_creation_is_announced(app):
    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert f"Created the database at {config.DB_PATH}" in result.output
    assert f"schema v{LATEST_VERSION}" in result.output


def test_upgrade_is_announced(app, monkeypatch):
    runner.invoke(app, ["probe"])

    def added(conn):
        conn.exec_driver_sql("CREATE TABLE added (id INTEGER)")

    latest = LATEST_VERSION + 1
    monkeypatch.setattr(migrations, "MIGRATIONS", [*migrations.MIGRATIONS, added])
    monkeypatch.setattr(migrations, "LATEST_VERSION", latest)

    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert (
        f"Upgraded the database from schema v{LATEST_VERSION} to v{latest}"
        in result.output
    )


def test_up_to_date_database_is_silent(app):
    runner.invoke(app, ["probe"])

    result = runner.invoke(app, ["probe"])

    assert result.exit_code == 0, result.output
    assert "Created" not in result.output
    assert "Upgraded" not in result.output
