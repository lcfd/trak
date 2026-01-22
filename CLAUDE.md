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
├── main/
│   ├── routes.py        # Main callback - DB engine init, settings loading
│   └── annotations.py   # CLI option annotations
├── sessions/
│   └── models.py        # Session, RunningSession, Category, Tag models
├── projects/
│   └── models.py        # Project model
├── customers/
│   └── models.py        # Customer model
└── _OLD/                # Previous implementation (reference only)
```

## Database Schema

```
Customer (id, name)
    └── Project (id, customer_fk, name, description, rate, archived)
            └── Session (id, project_fk, category_fk, tag_fk, start, end)

Category (id, name)
Tag (id, name)
RunningSession (id, project_fk, category_fk, tag_fk, start)  # No end time - active tracking
```

## CLI Commands (To Implement)

**Quick usage:**
- `trak start [project]` - Start time tracking
- `trak stop` - Stop current session
- `trak status` - Show current running session

**Data operations:**
- `trak create project|customer|category|tag` - Create entities
- `trak delete project|session|...` - Delete entities
- `trak edit project|session|...` - Edit entities

**Reporting:**
- `trak report [project] [--period]` - Generate time reports

**Other:**
- `trak config` - Manage settings
- `trak doctor` - Diagnostics and health checks

## Development

```bash
# Install dependencies
uv sync

# Run CLI
uv run trak [command]

# Run tests
uv run pytest
```

## File Locations

- Database: `~/.config/trak/db.sqlite3`
- Dev database: `~/.config/trak/dev_db.sqlite3`
- Settings: `~/.config/trak/settings.toml`

## Code Conventions

- SQLModel for all database models with `table=True`
- Rich panels for user feedback via `base_messages.py`:
  - `print_error(title, text)` - Red panel
  - `print_success(title, text)` - Green panel
  - `print_info(title, text)` - Blue panel
  - `print_warning(title, text)` - Orange panel
- Typer Context object (`ctx.obj`) stores:
  - `DB_ENGINE` - SQLModel engine for database access
  - `SETTINGS` - Dict from settings.toml
