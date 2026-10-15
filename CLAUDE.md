# Trak CLI

Time tracking CLI for freelancers. Track hours on projects, generate reports, and manage billing.

## Tech Stack

- Python 3.11+
- Typer (CLI framework)
- SQLModel (ORM)
- SQLite (database)
- Rich + rich-toolkit (UI)
- uv (package manager)

## Project Structure

```
trak/
├── __main__.py          # Entry point → calls typer_app.app
├── typer_app.py         # Typer app definition and command registration
├── config.py            # Paths and constants (APP_NAME, VERSION, DB_PATH)
├── base_messages.py     # Rich UI helpers (print_error, print_success, print_info, print_warning)
├── ui.py                # Additional UI utilities
├── dev_bar.py           # Green bar on top of every screen in dev mode; dev_bar.clear() clears keeping it
├── main/
│   ├── routes.py        # Main callback - settings, dev mode, DB engine, migrations
│   └── annotations.py   # CLI option annotations
├── db/
│   ├── engine.py        # get_engine(): SQLite engine (FKs on, transactional DDL)
│   └── migrations.py    # MIGRATIONS list + migrate(), versioned via PRAGMA user_version
├── browser.py           # Full-screen paginated list browser, shared by every entity
├── forms.py             # Edit form: menu of fields + Save, shared by every entity
├── entities.py          # EntityGroup (`trak <entities> ID`), get_or_pick, print_details
├── doctor.py            # `trak doctor`: DB path, schema version, integrity and FK checks
├── sessions/
│   ├── models.py        # Session, Category, Tag models
│   ├── services.py      # start/stop/update/list sessions, session_totals
│   ├── commands.py      # start, stop + shared CLI helpers (is_interactive, run_prompts, find_*)
│   ├── listing.py       # `sessions list` browser
│   ├── creating.py      # `sessions create` (backfill a past session)
│   ├── details.py       # `sessions show`
│   └── editing.py       # `sessions edit`
├── projects/            # models, services, listing (`list`), commands (create/show/edit/report),
│                        # report.py (ranges, per-day time, bar chart, the report screen)
├── customers/           # models, services, listing (`list`), commands (create/show/edit)
├── goals/               # models, services (progress), display (menu reminder), listing, commands
└── _OLD/                # Previous implementation (reference only)
tests/                   # pytest suite (conftest isolates paths and DBs in tmp_path)
```

## Database Schema

The Session is the base unit; every association is optional.

```
Session (id, name, customer_fk?, project_fk?, category_fk?, tag_fk?, start, end?, active)
Project (id, customer_fk?, name, description, rate, archived)
Customer (id, name)
Category (id, name)
Tag (id, name)
Goal (id, project_fk, name, hours, start, deadline)
```

- A Session can belong to a Project, to a Customer, both, or neither.
- A Project can belong to a Customer.
- A Goal is an aim, not an obligation: `hours` to track on a Project from `start`
  to `deadline` (dates, both included). Its progress is computed from the
  Project's Sessions started in that span (`goal_progress`), never stored.
- `active=True` means the Session is running: `end` is `None` until it's stopped.
  Multiple Sessions can be active at the same time.
- Datetimes must be timezone-aware (SQLModel enforces it); use `datetime.now(UTC)`.

## Migrations

No Alembic. `trak/db/migrations.py` holds an append-only `MIGRATIONS` list of
functions, and the schema version lives in SQLite's `PRAGMA user_version`.
`migrate()` runs on every command in the main callback; each pending migration
runs in its own transaction with its version bump. When it applies any, the
callback prints a dim one-liner on stderr ("Created the database…" /
"Upgraded the database from schema vN to vM"); `trak doctor` shows the version.

- Changing a model? Append a new migration written in plain SQL. Never edit
  a released one, never use `SQLModel.metadata.create_all`.
- `tests/test_migrations.py::test_migrations_match_models` fails if the
  migrated schema and the models diverge.

## CLI Commands (To Implement)

**Bare `trak`:** logo + upcoming goals (progress, days left) + a filterable menu of every command plus a `help` entry (`trak/main/menu.py`); without a TTY it prints the help.
The filter ranks abbreviations first (`command_score`): "sl" → sessions list, "se" → sessions edit, "pc" → projects create.

**Quick usage:**
- `trak start [project]` - Start time tracking
- `trak stop` - Stop current session
- `trak status` - Show current running session

**Entity groups** (`trak sessions|projects|customers|goals`, built with `trak/entities.py`):
- `trak <entities>` - Same as `trak <entities> list` with no options
- `trak <entities> ID` - Same as `trak <entities> show ID` (`EntityGroup` routes a number to `show`)
- `trak <entities> show|edit [ID]` - Without ID, pick it in the list browser (j/k + Enter, needs a TTY).
  `edit` opens a menu of fields (`trak/forms.py`; Esc discards) and always needs a TTY
- `trak sessions list [--project] [--customer] [--name] [--date|--from/--to] [--page] [--plain]` - Browse sessions (newest first); `--plain` or no TTY prints one page
- `trak projects list [--name] [--customer] [--archived] [--page] [--plain]` - Browse projects; `a` toggles archived in the browser
- `trak customers list [--name] [--page] [--plain]` - Browse customers
- `trak goals list [--project] [--all] [--page] [--plain]` - Browse goals, nearest deadline first;
  past ones only with `--all` (`a` toggles them in the browser)
- `trak projects create [NAME] [--customer] [--rate] [--description]` - Without NAME, asks every field (TTY)
- `trak projects report [ID] [--range] [--plain]` - Time tracked on a project as a bar chart.
  Without ID, pick it. In a TTY it stays open: h/l (Tab) switch range, 1-9 jump, r refresh.
  Ranges: since the start, last year, 6/3 months, last/this month, last week, last 7 days,
  this week; only the ones that differ from "since the start" and aren't empty. This month/week
  run to their last day (days to come on a dotted axis). Every day has a bar, empty ones too,
  and the chart shows even with nothing tracked. A bar is a
  day, or a week/month/year when the days don't fit. Sessions are split at local midnight
- `trak sessions create [PROJECT] [--start] [--end] [--name] [--customer]` - Backfill a past
  session. `--end` takes a time or a duration (`1h30m`), default now. With PROJECT,
  `--start` is required; with nothing, asks every field (TTY)
- `trak customers create [NAME]` - Without NAME, asks it (TTY)
- `trak goals create [PROJECT] [--hours] [--by DATE] [--from DATE] [--name]` - With PROJECT,
  `--hours` and `--by` are required; without it, asks every field (TTY).
  Dates: `YYYY-MM-DD`, `today`, `tomorrow`, `+N` (in N days)
- Every list browser is `trak/browser.py` with a per-entity `Listing` (query, table, filter shortcuts)

**Data operations (to implement):**
- `trak create category|tag` - Create entities
- `trak delete project|session|...` - Delete entities

**Reporting:**
- `trak report [project] [--period]` - Generate time reports

**Other:**
- `trak config` - Manage settings
- `trak doctor` - DB path, schema version vs latest, `integrity_check` and
  `foreign_key_check`; exits 1 on any problem

## Development

```bash
# Install dependencies
uv sync

# Run CLI
uv run trak [command]

# Run tests
uv run pytest

# Development mode: use the dev database instead of the real one
TRAK_DEV=1 uv run trak [command]
```

Development mode is on with `TRAK_DEV=1` or `development = true` (or `TRAK_DEV = true`) in
settings.toml. The env var wins (`TRAK_DEV=0` turns it off for one command).
`ctx.obj["DEV_MODE"]` tells commands whether it's on.

## Testing

The codebase must be covered by tests using pytest.

- Every new feature or bug fix comes with tests in `tests/`.
- Tests never touch the real settings or databases: the autouse
  `isolated_paths` fixture in `tests/conftest.py` redirects them to `tmp_path`.
- Use the `engine` / `db` fixtures for a migrated temporary database, and
  `typer.testing.CliRunner` for commands.

## Interactive UI: vim first

Design principle for every interactive UI: a vim/neovim user should feel at home.

- Build prompts with `trak/prompts.py` (`VimToolkit`, via `guided.make_prompter()`),
  never with rich-toolkit's `Menu`/`Input` directly.
- Filterable lists open in INSERT mode (typing filters); Esc switches to NORMAL mode:
  `j`/`k` move, `g`/`G` first/last, Ctrl-d/Ctrl-u half a screen, `i` resumes the
  filter, `/` starts a new one, Enter picks, Esc/`q` go back. Other lists are always
  in NORMAL mode (`h`/`l` for inline ones).
- Text inputs: Esc goes back without changes; Ctrl-u clears, Ctrl-w deletes a word.
- Going back raises `PromptCancelled`: callers decide what it means (keep the old
  value, or print "Cancelled" and exit 1).
- Full-screen views (like `trak sessions list`) use single keys with vim bindings
  first (`h`/`l` pages, `g`/`G`, `/` search, `q` quit), list them in a `?` help,
  and hide the cursor while waiting for a key.

## File Locations

Follows XDG (`$XDG_DATA_HOME` / `$XDG_CONFIG_HOME` override the defaults):

- Database: `~/.local/share/trak/db.sqlite3`
- Dev database: `~/.local/share/trak/dev_db.sqlite3`
- Settings: `~/.config/trak/settings.toml`

## Code Conventions

- SQLModel for all database models with `table=True`
- Rich panels for user feedback via `base_messages.py`:
  - `print_error(title, text)` - Red panel
  - `print_success(title, text)` - Green panel
  - `print_info(title, text)` - Blue panel
  - `print_warning(title, text)` - Orange panel
- Typer Context object (`ctx.obj`) stores:
  - `DB_ENGINE` - SQLModel engine for database access (already migrated)
  - `SETTINGS` - Dict from settings.toml
  - `DEV_MODE` - True when using the dev database
- Read paths as `config.DB_PATH` (module attribute), not `from trak.config import DB_PATH`,
  so tests can monkeypatch them.
