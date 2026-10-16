<p align="center">
  <a href="https://github.com/lcfd/trak">
    <img src="https://raw.githubusercontent.com/lcfd/trak/main/assets/banner.png" alt="Trak banner">
  </a>

  <h1 align="center">trak</h1>

  <p align="center">
    <br />
    Trak is a CLI to track the time you spend on projects, with useful reports and analytics.
    <br />
    <br />
    For freelancers, by a freelance.
    <br />
    <br />
    <a href="https://usetrak.com">Website</a>
    ·
    <a href="https://github.com/lcfd/trak/issues">Issues</a>
    ·
    <a href="https://docs.usetrak.com">Documentation (🏗️)</a>
    •
    <a href="https://github.com/lcfd/trak/discussions">Feedback</a>
  </p>
</p>

## Installation

### Pypi

[On Pypi](https://pypi.org/project/trakcli/) you can find the package under the `trakcli` name.

You can install it with pip:

```bash
pip install trakcli
```

or with `pipx`:

```bash
pipx install trakcli
```

### Brew

`brew install lcfd/trak/trak`

### Nix

If you have [Nix](https://nixos.org/download.html) installed and flakes enabled, you can try trak using:

```bash
nix run github:lcfd/trak
```

The package will be built from source, so it might take a while.

You can pass arguments like this:

`nix run github:lcfd/trak -- --help`

### Local

Run `uv build` and then

```bash
# x.x.x = The version you have used to do the build.
uv tool install ./dist/trakcli-x.x.x-py3-none-any.whl
```

to install `trak` using the wheel file.

## Usage

Run `trak` alone to open a menu of every command: type to filter it
(abbreviations work, e.g. `sl` → `sessions list`, `pc` → `projects create`)
and press Enter to run one. Without a terminal it prints the help.

Every command explains itself with `--help`:

`trak --help`

### Tracking time

```bash
# Start a session on a project (leave it empty to pick one)
trak start <project-name>

# Give the session a name
trak start <project-name> --name "Fix the login page"

# Fill in every field of the session interactively
trak start --guided

# Stop the active session (if more are running, pick one)
trak stop

# Stop only the sessions of a project, or all of them at once
trak stop <project-name>
trak stop --all
```

A session can belong to a project or directly to a customer, or to neither.
A session on a project belongs to the project's customer too.
More than one session can run at the same time.

### Your data

Sessions, projects and customers share the same commands:

```bash
trak sessions            # Browse them (same as `trak sessions list`)
trak sessions 42         # Show one (same as `trak sessions show 42`)
trak sessions show       # Pick one in the list, then show it
trak sessions edit [ID]  # Edit one in a menu of its fields
```

Swap `sessions` with `projects` or `customers`.

Filter the lists with options:

```bash
trak sessions list --project pasta --from 2026-10-01 --to 2026-10-14
trak sessions list --customer acme --date 2026-10-14
trak projects list --customer acme --archived
trak customers list --name ac
```

Add `--plain` to print one page instead of opening the browser
(`--page` and `--per-page` pick which one).

Create projects and customers:

```bash
trak customers create acme
trak projects create pasta --customer acme --rate 50 --description "The website"

# Without a name, trak asks for every field
trak projects create
```

### Vim keys

Every interactive screen feels like vim:

- Lists: `j`/`k` move, `g`/`G` go to the first/last row, `h`/`l` change page,
  `/` searches, Enter picks, `q` quits and `?` shows every shortcut.
- Filterable menus start in insert mode (typing filters); Esc switches to
  normal mode, `i` resumes the filter.
- Text inputs: Esc goes back without changes, Ctrl-u clears, Ctrl-w deletes a word.

## Where your data lives

trak follows XDG (`$XDG_DATA_HOME` and `$XDG_CONFIG_HOME` override the defaults):

- Database: `~/.local/share/trak/db.sqlite3`
- Settings: `~/.config/trak/settings.toml`

The database is upgraded automatically when you install a new version.

## Starship

Show the running session in your prompt with [Starship](https://starship.rs).

`trak status -s` (or `trak status --starship`) prints one plain line:

```
website 1h 23m +1
```

That's the session you started last, how long it has been running, and how many
other sessions are running (`+1`). In development mode the line ends with `(dev)`.
When nothing is running it prints nothing.

Open `~/.config/starship.toml` and add:

```toml
[custom.trak]
command = "trak status -s"
when = true
shell = ["sh"]
```

Use `when = true`, not a command like `when = "trak status"`. Starship already
hides the module when `trak status -s` prints nothing, so the extra check would
only run trak a second time on every prompt.

`trak status -s` is built for this and answers in a few tens of milliseconds,
well within Starship's default 500 ms `command_timeout`. If Starship still warns
that the command timed out, check that the `trak` on your `PATH` is up to date
(`trak --version`).

## Distribution

### Create dist tar

`tar --exclude=".venv" --exclude="dist" --exclude=".mypy_cache" --exclude=".pytest_cache" --exclude="**/__pycache__" -czvf dist.tar.gz cli`

## How to contribute to the project

### Things you should know

Every version has its own dedicated branch.

For example: `0.0.6`.
All the changes done during this version development time will go into this branch.

### Development setup

trak needs Python 3.11+ and uses [uv](https://docs.astral.sh/uv/).

```bash
# Install the dependencies
uv sync

# Run the CLI
uv run trak [command]

# Use the development database instead of the real one
TRAK_DEV=1 uv run trak [command]

# Run the tests
uv run pytest
```

Development mode can also be turned on with `development = true` (or `TRAK_DEV = true`) in
`settings.toml`; `TRAK_DEV=0` turns it off for one command.

Every new feature or bug fix comes with tests in `tests/`.
Changing a model? Append a migration to `trak/db/migrations.py`.

### Steps

- Pick an issue from the Issues
  - If it doesn't exist create one
- Create a branch starting from the next version branch
  - The name of the issue should be `issue-<ISSUE NUMBER>`
- Do your magic 🪄 🐇
- Once you finish create a pull request to the next version branch
  - In the description add `Closes #<ISSUE NUMBER>`
- The maintainer will do a review of the changes
- Done! 🎉
