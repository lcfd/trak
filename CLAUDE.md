# Trak CLI

Time tracking CLI for freelancers. Track hours on projects, generate reports, and manage billing.

## Tech Stack

- Python 3.11+
- Typer (CLI framework)
- SQLModel (ORM)
- SQLite (database)
- Rich (UI); rich-toolkit only for its key reader and the `Option` type
- uv (package manager)

## Project Structure

```
trak/
├── __main__.py          # Entry point → calls typer_app.app
├── typer_app.py         # Typer app definition and command registration
├── config.py            # Paths and constants (APP_NAME, VERSION, DB_PATH)
├── base_messages.py     # Rich UI helpers (print_error, print_success, print_info, print_warning)
├── output.py            # --json: JSON mode, emit(), errors on stderr, the option on every command
├── dates.py             # Days typed by the user (YYYY-MM-DD, today, tomorrow, +N)
├── dev_bar.py           # Green bar on top of every screen in dev mode; dev_bar.clear() clears keeping it
├── tui.py               # Full screen: open_screen() (Terminal, or PlainScreen without a TTY), page(), overlay()
├── panes.py             # Lazygit-style panes (Pane, Item, render, side_by_side, tabs): home and show views
├── views.py             # DetailView: the two-pane `show` of sessions, goals, projects; show_in(), run()
├── clipboard.py         # copy(): pbcopy/wl-copy/xclip/xsel/clip.exe, else OSC 52 (`y` in views)
├── prompts.py           # ScreenPrompter: full-screen vim prompts (Menu, TextInput), answers listed above
├── main/
│   ├── routes.py        # Main callback - settings, dev mode, DB engine, migrations
│   ├── menu.py          # run_menu: opens the home; the commands it lists (collect_commands, command_score)
│   ├── home.py          # The home of a bare `trak`: Goals, Sessions, Actions panes (lazygit style)
│   ├── overview.py      # `trak --json` alone: version, running sessions, upcoming goals
│   └── annotations.py   # CLI option annotations
├── db/
│   ├── engine.py        # get_engine(): SQLite engine (FKs on, transactional DDL)
│   └── migrations.py    # MIGRATIONS list + migrate(), versioned via PRAGMA user_version
├── browser.py           # Full-screen paginated list browser, shared by every entity (pages fit the height)
├── tables.py            # Tables that fit the width: a ladder of layouts per list (group, shorten, drop)
├── forms.py             # Edit form: menu of fields + Save, shared by every entity
├── entities.py          # EntityGroup (`trak <entities> ID`), get_or_pick, print_details, save_changes
├── doctor.py            # `trak doctor`: DB path, schema version, integrity and FK checks
├── dev/                 # `trak dev` (in --help, not in the menu: `NOT_IN_MENU` in main/menu.py)
│   ├── commands.py      # `trak dev fill`
│   └── fill.py          # Years of made-up data relative to today (projects, sessions, goals)
├── labels/              # Categories and Tags
│   ├── links.py         # Tags of Sessions/Projects/Customers (link tables), with_tags, labels_json
│   ├── services.py      # Kind (CATEGORY, TAG) + create/update/list/delete, shared by both
│   ├── listing.py       # `categories|tags list` browser, label_json
│   └── commands.py      # make_app(kind): list/show/create/edit/delete
├── sessions/
│   ├── models.py        # Session, Category, Tag, SessionTag/ProjectTag/CustomerTag models
│   ├── services.py      # start/stop/update/list sessions, session_totals
│   ├── commands.py      # start, stop, status + shared CLI helpers (is_interactive, run_prompts,
│   │                    # find_*, association_fks, session_customer_fk, fail)
│   ├── listing.py       # `sessions list` browser
│   ├── creating.py      # `sessions create` (backfill a past session)
│   ├── view.py          # `sessions show`: SessionView, session_rows, show_command
│   └── editing.py       # `sessions edit`
├── projects/            # models, services, listing (`list`), commands (create/edit/report),
│                        # view.py (`show`), report.py (ranges, per-day time, bar chart, the report screen)
├── customers/           # models, services, listing (`list`), commands (create/show/edit)
└── goals/               # models, services (progress), display (progress texts), listing,
                         # commands (create/edit), view.py (`show`)
tests/                   # pytest suite (conftest isolates paths and DBs in tmp_path)
```

## Database Schema

The Session is the base unit; every association is optional.

```
Session (id, name, customer_fk?, project_fk?, category_fk?, start, end?, active)
Project (id, customer_fk?, name, description, rate, archived, start?, end?, category_fk?)
Customer (id, name, category_fk?)
Category (id, name)
Tag (id, name)
SessionTag (session_fk, tag_fk) / ProjectTag (project_fk, tag_fk) / CustomerTag (customer_fk, tag_fk)
Goal (id, project_fk, name, hours, start, deadline)
```

- Sessions, Projects and Customers have one optional Category and any number of
  Tags (link tables, `trak/labels/links.py`). Services, forms and flags handle the
  Tags as a `tag_fks` field (sorted ids; `with_tags(db, row)` adds it to a row for
  `forms.current`/`effective_changes`); the JSON has `category`, `tag_fks`, `tags`.
  Category and Tag names are unique and have no commas.

- A Session can belong to a Project, directly to a Customer, or neither. A
  Session on a Project belongs to the Project's Customer (`session_customer_fk`
  stores no `customer_fk` then); a direct Customer is only for Sessions whose
  Project has none.
- A Project can belong to a Customer, and can run from `start` to `end` (dates,
  both included, each optional). They're informative: Sessions outside them are fine.
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

## Every command: flags first, JSON for tools

The interactive UI is a convenience on top of the flags, never the only way in.
Apply these to every new command and every new field.

**Flag parity.** Anything a prompt, a form or a browser can set has a flag, so
every command works in one line, without a terminal (scripts, editors, cron):
- A new model field gets a flag on `create` and on `edit`, a row in `show`, a
  key in the JSON, and (if useful) a column/filter in `list`.
- Associations are flags taking a name (`--project website`, `--customer ACME`),
  looked up with `find_*` (an error lists the available names). On `edit`, an
  empty value clears an optional field (`--customer ""`, `--end ""`). Booleans
  are pairs (`--archive/--unarchive`); flags left out (None) change nothing.
- `edit ID --field value ...` saves right away, no terminal needed; `edit`
  without flags opens the form (needs a terminal). Both validate through the same
  service function, and `entities.save_changes` reports both ("saved",
  "Nothing changed", the error).
- Prompts run only in a terminal and only when a required value is missing; they
  start from what the flags gave (as defaults). Without a terminal the error
  names the missing flag (e.g. "Give its start with --start").
- Picking a row (no ID) needs a terminal; with an ID it never does.

**`--json` on every command** (`trak/output.py`; `TrakGroup` in `typer_app.py`
adds it to every command and group, so new commands get it for free, and
`tests/test_json.py` checks it):
- stdout holds exactly one JSON document on one line, and nothing else. Panels
  (`print_success/info/warning`) print nothing; `print_error` writes
  `{"error": {"title", "message"}}` (plain text, no markup) on stderr, exit 1.
  No dev bar, no migration notice. Click usage errors stay plain text, exit 2.
- JSON mode never prompts and never opens a browser: `is_interactive()` is
  False, so whatever needs a terminal is an error.
- Commands call `output.emit(data)` next to their panel (it does nothing
  outside JSON mode): `create`/`show`/`edit` (even "Nothing changed") emit the
  entity; `list` emits `{"items", "total", "page", "pages", "per_page"}` through
  `browser.print_page` and the `Listing.to_json` of the entity; actions emit
  what they touched (`start` the session, `stop` and `status` a list, empty if
  none); `trak --json` alone emits the overview.
- An entity is `output.fields(row)` (every model field, `*_fk` included, in
  model order), plus the names of its associations (`"project": "website"`),
  plus computed values (`tracked_seconds`, `days_left`...). Each entity has one
  `<entity>_json()` used everywhere.
- Values: datetimes ISO 8601 in local time with the offset, dates `YYYY-MM-DD`,
  durations whole seconds in `*_seconds` keys, missing values `null`. The JSON
  never depends on the terminal (e.g. the report has one entry per day).

## CLI Commands (To Implement)

**Bare `trak`:** the home (`trak/main/home.py`), lazygit style: the whole terminal (alt screen),
redrawn on resize, in three panes reachable with `1` `2` `3` (and `h`/`l`, Tab): **Goals** (upcoming,
progress, days left), **Sessions** (running first, then recent ones by day), **Actions** (every
command plus `help` and `quit`). The focus starts on Actions. `j`/`k`/`g`/`G`/Ctrl-d/Ctrl-u move,
Enter shows the goal/session or runs the action, `e` edits, `n` new goal / start, `s` stops the
running session in place, `/` filters the actions (`command_score`), `?` help, `q` quits. Commands
run on the normal screen, then any key comes back (`q` quits; `list`/`report` and the
sessions/goals/projects `show` views come back directly, `home.is_view`). Below 96 columns one pane shows at a time, with the three as tabs. Without a TTY it
prints the help; with `--json`, the overview (`main/overview.py`). Tests drive it with a
`FakeScreen` (`tests/test_home.py`).
The filter ranks abbreviations first (`command_score`): "sl" → sessions list, "se" → sessions edit, "pc" → projects create.

**Quick usage:**
- `trak start [PROJECT] [--name] [--customer] [--category] [--tag]... [--start] [-g]` - Start a
  session. In a terminal, with no project or other association, asks the project; `-g` asks
  every field starting from the flags. A project's customer applies to its sessions: another
  `--customer` is an error (`session_customer_fk`)
- `trak stop [PROJECT] [--all] [--id ID]` - Stop a running session; with several, picks one
  (terminal) or needs `--id`/`--all`
- `trak status` - The running sessions (`--json`: a list, for statuslines)

**Entity groups** (`trak sessions|projects|customers|goals`, built with `trak/entities.py`):
- `trak <entities>` - Same as `trak <entities> list` with no options
- `trak <entities> ID` - Same as `trak <entities> show ID` (`EntityGroup` routes a number to `show`)
- `trak <entities>` are sessions, projects, customers, goals, categories, tags
- `trak sessions|goals|projects show [ID] [--plain]` - In a terminal, full screen in two panes
  like the home (`views.DetailView`): [1] the row (where the focus starts; `e` edits it in
  place) and [2] sessions by day (j/k, Enter shows one). Sessions: [2] is its project's
  sessions, Enter shows one in place (Esc/Ctrl-o back), `s` stops it. Goals: progress bar and
  pace in [1], [2] the sessions counted. Projects: its goals in [1], [2] its sessions, `R` its
  report. `--plain`, no TTY or `--json` print the details panel. Customers, categories and
  tags `show` print a panel
- `trak <entities> show|edit [ID]` - Without ID, pick it in the list browser (j/k + Enter, needs a TTY).
  `edit` takes a flag per field and saves them; without flags it opens a menu of fields
  (`trak/forms.py`; Esc discards), which needs a TTY
- `trak sessions list [--project] [--customer] [--category] [--tag] [--name] [--date|--from/--to] [--page] [--per-page] [--plain]` - Browse sessions (newest first); `--plain` or no TTY prints one page
- `trak projects list [--name] [--customer] [--archived] [--page] [--per-page] [--plain]` - Browse projects; `a` toggles archived in the browser
- `trak customers list [--name] [--page] [--per-page] [--plain]` - Browse customers
- `trak categories|tags list|show|create|edit|delete` - One implementation for both
  (`labels/commands.py`, `make_app(kind)`). `delete [ID] [--yes]` takes it off every session,
  project and customer; it asks in a terminal, needs `--yes` without one
- `trak goals list [--project] [--all] [--page] [--per-page] [--plain]` - Browse goals, nearest deadline first;
  past ones only with `--all` (`a` toggles them in the browser)
- `trak projects create [NAME] [--customer] [--category] [--tag]... [--rate] [--description] [--start DATE] [--end DATE]` -
  Without NAME, asks every field (TTY). Show, edit and list (Dates column) cover the dates too
- `trak projects report [ID] [--range | --from DATE --to DATE] [--plain]` - Time tracked on a
  project as a bar chart (`--json`: any range, with the time of every day). `--from`/`--to`
  (from the project's first day, to today by default) add a "Custom" tab first.
  Without ID, pick it. In a TTY it stays open: Tab/S-Tab (`]`/`[`) switch range, 1-9 jump,
  h/l/g/G select a bar, Enter zooms into it one unit down (a year shows its months, a month
  its weeks, a week its days; `Range.unit`), Esc zooms out (quits when not zoomed), r refresh.
  "Since the start" runs from the project's start (or first session, if earlier) to its end
  when that's still to come. Ranges: since the start, last year, 6/3 months, last 30 days, this month, last week, last 7 days,
  this week; only the ones that differ from "since the start" and aren't empty (none after
  the project's last session, start or end). This month/week
  run to their last day (days to come on a dotted axis). Every day has a bar, empty ones too,
  and the chart shows even with nothing tracked. A bar is a
  day, or a week/month/year when the days don't fit. Sessions are split at local midnight
- `trak sessions create [PROJECT] [--start] [--end] [--name] [--customer] [--category] [--tag]...` -
  Backfill a past session. `--end` takes a time or a duration (`1h30m`), default now.
  Without `--start`, asks every field (TTY), starting from the flags
- `trak sessions edit [ID] [--name] [--project] [--customer] [--category] [--tag]... [--start] [--end]`
  (`--end` stops a running session)
- `--tag` everywhere: repeat it or separate names with commas (`-t billable,urgent`); on
  `edit` it replaces the tags, `--tag ""` clears them (`commands.find_tags`). Prompts pick
  tags with `guided.pick_many` (Enter toggles, Done ends)
- `trak projects edit [ID] [--name] [--customer] [--category] [--tag]... [--rate] [--description] [--start] [--end]
  [--archive/--unarchive]`; `trak customers edit [ID] [--name] [--category] [--tag]...`;
  `trak goals edit [ID] [--project] [--name] [--hours] [--from] [--by]`
- `trak customers create [NAME] [--category] [--tag]...` - Without NAME, asks every field (TTY)
- `trak goals create [PROJECT] [--hours] [--by DATE] [--from DATE] [--name]` - Needs PROJECT,
  `--hours` and `--by` (which defaults to the project's end); with any missing, asks
  every field (TTY) starting from the flags, offering the project's end as the deadline.
  Dates (`trak/dates.py`, for goals and projects): `YYYY-MM-DD`, `today`, `tomorrow`, `+N` (in N days)
- A `show` with a two-pane view lives in `<entity>/view.py`, always the same three things:
  the `<Entity>View` (a `views.DetailView`), `<entity>_rows(db, row)` (the details, for the
  view and the `--plain` panel) and `show_command`. `view.py` imports `commands.py`, never the
  other way; `listing.py` imports the view inside its `show_<entity>` (the view imports it).
- Every list browser is `trak/browser.py` with a per-entity `Listing` (query, table, to_json, filter shortcuts,
  `show`/`edit` of a row). Rows are always selectable: j/k move a highlighted row across pages,
  g/G first/last row, Enter shows it (the views above on the same screen, via `views.show_in`,
  which ends the browser's read first; panels via `entities.show_printed`), `e` edits it in
  place (`entities.edit_in_place`), `y` copies its id; when picking, Enter returns it. A page is
  queried and its table fit once (cursor moves restyle a row), and keys already typed are all
  handled before the next frame, so holding j/k doesn't lag;
  the table comes from `Listing.cells` (a row's cells, computed once) and `Listing.layouts` (`tables.py`)

**Data operations (to implement):**
- `trak delete project|session|...` - Delete entities

**Reporting:**
- `trak report [project] [--period]` - Generate time reports

**Other:**
- `trak config` - Manage settings
- `trak doctor` - DB path, schema version vs latest, `integrity_check` and
  `foreign_key_check`; exits 1 on any problem (`--json`: the same, `problems` a list)
- `trak dev fill [--years 6] [--seed N] [--reset]` - Fill the dev database (always
  `dev_db.sqlite3`, dev mode or not) with years of data up to today: thousands of
  sessions, past/current/future projects and goals, two running sessions, categories and
  tags on sessions, projects and customers. Refuses a
  dev database with data unless `--reset`. `dev` is in --help, not in the menu

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

- Every new feature or bug fix comes with tests in `tests/`, including its flags
  (`tests/test_flags.py`) and its JSON (`tests/test_json.py`).
- Tests never touch the real settings or databases: the autouse
  `isolated_paths` fixture in `tests/conftest.py` redirects them to `tmp_path`.
- Use the `engine` / `db` fixtures for a migrated temporary database, and
  `typer.testing.CliRunner` for commands.

## Interactive UI: vim first

Design principle for every interactive UI: a vim/neovim user should feel at home.

- **Full screen, lazygit style.** Every interactive screen (home, browsers, the
  report, prompts, forms) takes the whole terminal through `trak/tui.py`: the
  alternate screen (the shell comes back untouched; panels printed after a view,
  like "saved", land on the normal screen), the dev bar on top, `tui.header`, one
  green panel (`tui.page`) and a footer of key hints (`tui.hints`). Draw whole
  frames sized to `screen.size()`; `read_key` returns None on a resize: draw again.
  Below 30x8 a view says "Make the terminal bigger". Nested views (a filter asked
  in a browser) reuse the open screen (`tui.open_screen`).
- Lists fill the height: without `--per-page`, a page has as many rows as fit
  (`browser.rows_that_fit`), recomputed on resize; rows stay on one line.
- Tables fit their width by changing layout, never with scrollbars or wrapping
  (`trak/tables.py`). Each list declares a ladder of layouts, widest first: the
  table takes the first whose columns fit whole, only `flex` columns (names,
  labels) shrinking to their `least`. Narrower layouts group related columns
  (Start + End → When `15 Oct 09:00–10:30`, Project · Customer, Category + Tags →
  Labels), then use shorter formats (`tables.short_day`), then drop what matters
  least (it's in `show`). Ids, dates, numbers and durations are never cut;
  `optional` columns leave when empty on the page. A new column goes in the
  widest layout and wherever it still earns its room.
- Without a terminal (tests), `tui.PlainScreen` prints each frame below the last;
  `tests/fakes.py` has `FakeScreen` (scripted keys and resizes) and `frames()`.
- Build prompts with `trak/prompts.py` (`ScreenPrompter`, via `guided.make_prompter()`),
  never with rich-toolkit's `Menu`/`Input` directly. Each question is a full
  screen titled with the command, the answers so far listed above it.
- Filterable lists open in INSERT mode (typing filters); Esc switches to NORMAL mode:
  `j`/`k` move, `g`/`G` first/last, Ctrl-d/Ctrl-u half a screen, `i` resumes the
  filter, `/` starts a new one, Enter picks, Esc/`q` go back. Other lists are always
  in NORMAL mode (`h`/`l` for inline ones).
- Text inputs: Esc goes back without changes; Ctrl-u clears, Ctrl-w deletes a word.
- Going back raises `PromptCancelled`: callers decide what it means (keep the old
  value, or print "Cancelled" and exit 1).
- The home's Actions pane is the exception: it starts in NORMAL mode, so the digits
  switch panes; `/` starts the filter, Esc stops it, Esc again clears it.
- `y` copies the id of what's focused (`clipboard.copied`, said in the footer with what it
  is: "Copied 12 · session"): in a two-pane view, [1] the row shown, [2] the session under the
  cursor (nothing if the list is empty); the row under the cursor in the home's panes and every
  list browser; the report's project. A home action copies `trak <command>`. The hint names
  it too ("y copy goal id"), changing with the focus.
- Full-screen views (like `trak sessions list`) use single keys with vim bindings
  first (`h`/`l` pages, `g`/`G`, `/` search, `q` quit), list them in a `?` help
  (`tui.overlay`), and hide the cursor (`tui.Terminal` does it).

## File Locations

Follows XDG (`$XDG_DATA_HOME` / `$XDG_CONFIG_HOME` override the defaults):

- Database: `~/.local/share/trak/db.sqlite3`
- Dev database: `~/.local/share/trak/dev_db.sqlite3`
- Settings: `~/.config/trak/settings.toml`

## Code Conventions

- SQLModel for all database models with `table=True`
- Rich panels for user feedback via `base_messages.py` (JSON-aware, see above):
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
