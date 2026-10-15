"""
The `show` views of sessions, goals and projects: full screen, two panes like
the home. [1] is the row (its details), [2] a list of sessions that belong to
it, by day.

    ┌[1] Session────────────┐┌[2] Sessions of website─────────┐
    │Landing page           ││Today                           │
    │                       ││▸ 09:12   2h 3m  Landing page   │
    │Id        42  y copies ││  08:00   1h 0m  Standup        │
    │Project   website      ││Yesterday                       │
    └───────────────────────┘└────────────────────────────────┘
     y copy id · e edit · 1-2 panes · ? help · q quit

The focus starts on [1]. On [2], j/k move and Enter shows the session. `y`
copies the id of what's selected: the session under the cursor on [2], the
row itself on [1]. `e` edits the row, on the same screen.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlalchemy import Engine
from sqlmodel import Session as DBSession

from trak import clipboard, panes, tui
from trak.panes import CTRL_D, CTRL_O, CTRL_U, DOWN, ENTER, LEFT, RIGHT, UP
from trak.prompts import PromptCancelled
from trak.sessions import commands
from trak.sessions.display import labels_text, session_line
from trak.sessions.models import Session

# Below this width the panes don't fit side by side: one at a time.
WIDE = 96
# How many sessions the list pane holds, newest first.
SESSIONS = 300
# Reload this often (seconds), so running times move.
REFRESH = 30
BACK = (tui.ESC, CTRL_O, *panes.BACKSPACE)


class SessionListPane(panes.Pane):
    """Sessions by day, newest first; the one on screen (if any) is marked ▸."""

    key = "2"
    hints = (("Enter", "show"),)

    def __init__(self) -> None:
        super().__init__()
        self.title = "Sessions"
        self.empty = "[dim]No sessions.[/dim]"
        self.current: int | None = None
        # (session, what it is, its category and tags)
        self.sessions: list[tuple[Session, str, str]] = []

    def load(
        self,
        db: DBSession,
        sessions: list[Session],
        describe: Callable[[Session], str] = lambda s: s.name or "(no name)",
        current: int | None = None,
    ) -> None:
        """The sessions to list; the cursor goes on `current` when it changes."""

        moved = current != self.current
        self.current = current
        self.sessions = [(s, describe(s), labels_text(db, s)) for s in sessions]
        if moved:
            ids = [s.id for s, _, _ in self.sessions]
            self.cursor = ids.index(current) if current in ids else 0
            self.offset = 0
        self.cursor = max(0, min(self.cursor, len(self.sessions) - 1))

    def items(self, width: int, now: datetime) -> list[panes.Item]:
        items: list[panes.Item] = []
        today = now.astimezone().date()
        day = None
        for session, name, labels in self.sessions:
            started = session.start.astimezone().date()
            if started != day:
                day = started
                if items:
                    items.append(panes.Item([Text()]))
                items.append(panes.heading(panes.day_label(day, today)))
            line = session_line(
                session, name, now, labels, current=session.id == self.current
            )
            items.append(panes.Item([line], session.id))
        return items


class DetailView:
    """
    A row in two panes. Subclasses fill the details and the list (`fill`), and
    say how to edit the row (`ask_edits`, `update`).
    """

    model: Any
    # [1]'s title ("Session"), and the noun in messages.
    title = ""
    noun = ""
    # [2]'s tab, when one pane shows at a time.
    tab = "Sessions"
    # What [2] lists, for the help.
    listing = "sessions"

    def __init__(
        self, engine: Engine, row_id: int, now: Callable[[], datetime] | None = None
    ) -> None:
        self.engine = engine
        self.row_id = row_id
        self.now = now or (lambda: datetime.now(UTC))
        # 0: the details, 1: the list.
        self.focus = 0
        self.message = ""
        self.list = SessionListPane()
        self.headline = ""
        self.rows: list[tuple[str, str]] = []
        # Markup lines below the rows (e.g. a progress bar, the goals).
        self.extra: list[str] = []
        self.loaded = 0.0

    # What subclasses say.

    def fill(self, db: DBSession, row: Any) -> None:
        """Set `headline`, `rows`, `extra`, and load `list`."""

        raise NotImplementedError

    def ask_edits(self, db: DBSession, prompter: Any, row: Any) -> dict[str, Any]:
        raise NotImplementedError

    def update(self, db: DBSession, row: Any, **changes: Any) -> Any:
        raise NotImplementedError

    def key(self, screen: tui.Screen, key: str) -> bool:
        """Keys of this view only; True if `key` was one."""

        return False

    def extra_hints(self) -> list[tuple[str, str]]:
        return []

    def extra_help(self) -> list[tuple[str, str]]:
        return []

    def back(self) -> bool:
        """Esc: go back to what was shown before; False if nothing was."""

        return False

    def open(self, screen: tui.Screen, session_id: int) -> None:
        """Enter on [2]: the session's own view, on the same screen."""

        from trak.sessions.view import SessionView

        SessionView(self.engine, session_id, now=self.now).loop(screen)
        self.load()

    # Data.

    def load(self) -> None:
        with DBSession(self.engine) as db:
            row = db.get(self.model, self.row_id)
            if row is None:
                raise LookupError(self.row_id)
            self.extra = []
            self.fill(db, row)
            self.rows.insert(0, ("Id", str(self.row_id)))
        self.loaded = monotonic()

    # Drawing.

    def details(self, console: Console, width: int, height: int) -> tui.Frame:
        label_width = max(len(label) for label, _ in self.rows)
        lines = [Text(self.headline, style="bold green"), Text()]
        lines += [
            Text.from_markup(f"[dim]{escape(label):<{label_width}}[/dim]  {value}")
            for label, value in self.rows
        ]
        if self.extra:
            lines += [Text(), *(Text.from_markup(line) for line in self.extra)]
        return panes.box(
            console,
            f"[1] {self.title}",
            panes.fit_lines(lines, max(1, width - 4)),
            width,
            height,
            focused=self.focus == 0,
        )

    def hints(self) -> list[tuple[str, str]]:
        pairs = [
            ("y", f"copy {self.copied_noun()} id"),
            ("e", "edit"),
            *self.extra_hints(),
        ]
        if self.focus == 1:
            pairs += [*self.list.hints, ("j/k", "move")]
        return [*pairs, ("1-2", "panes"), ("?", "help"), ("q", "quit")]

    def frame(self, console: Console, width: int, height: int) -> tui.Frame:
        now = self.now()
        if tui.too_small(width, height):
            return tui.small_frame(console, width, height)
        wide = width >= WIDE

        right = Text()
        if not wide:
            right = panes.tabs([("1", self.title), ("2", self.tab)], self.focus)
        right.append(f"{now.astimezone():%a %d %b %H:%M} ", style="dim")
        top = [*tui.top_lines(width), tui.line(tui.header(width, right), width)]
        body_height = height - len(top) - 1

        def listing(w: int) -> tui.Frame:
            return panes.render(
                console,
                self.list,
                w,
                body_height,
                now,
                focused=self.focus == 1,
                title=f"[2] {self.list.title}",
            )

        if wide:
            left = max(44, width * 2 // 5)
            body = panes.side_by_side(
                [self.details(console, left, body_height), listing(width - left)]
            )
        elif self.focus == 0:
            body = self.details(console, width, body_height)
        else:
            body = listing(width)

        footer = (
            Text.from_markup(f" {self.message}")
            if self.message
            else tui.hints(self.hints())
        )
        return [*top, *body, tui.line(footer, width)]

    def help(self) -> Panel:
        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold cyan", justify="right")
        grid.add_column()
        rows: Sequence[tuple[str, str]] = [
            ("1  2", f"The {self.noun}, its {self.listing}"),
            ("h  l  Tab", "Previous, next pane"),
            ("j  k  ↓  ↑", "Next, previous session"),
            ("g  G", "First, last session"),
            ("Ctrl-d  Ctrl-u", "Half a pane down, up"),
            ("Enter", "Show the session"),
            ("y", f"Copy the id of what's focused: the {self.noun}, or the session"),
            ("e", f"Edit the {self.noun}"),
            *self.extra_help(),
            ("r", "Reload"),
            ("?", "Show these shortcuts"),
            ("q", "Quit"),
        ]
        for keys, description in rows:
            grid.add_row(keys, description)
        return Panel(
            grid,
            title="[bold]Shortcuts[/bold]",
            subtitle="[dim]any key to close[/dim]",
            padding=(1, 3),
            expand=False,
        )

    # Actions.

    def copied_noun(self) -> str:
        """What `y` copies the id of: the focused pane's."""

        return "session" if self.focus == 1 else self.noun

    def copy(self, screen: tui.Screen) -> None:
        """
        The id of what's focused: on [1] the row shown, on [2] the session
        under the cursor (nothing if the list is empty).
        """

        if self.focus == 0:
            row_id = self.row_id
        else:
            row_id = self.list.selected(self.now())
            if row_id is None:
                self.message = "[yellow]No session selected.[/yellow]"
                return
        self.message = clipboard.copied(
            str(row_id), screen.console, what=self.copied_noun()
        )

    def edit(self) -> None:
        with DBSession(self.engine) as db:
            row = db.get(self.model, self.row_id)
            assert row is not None
            try:
                with commands.make_prompter() as prompter:
                    changes = self.ask_edits(db, prompter, row)
            except PromptCancelled:
                self.message = "[dim]No changes were saved.[/dim]"
                return
            if not changes:
                self.message = "[dim]Nothing changed.[/dim]"
                return
            try:
                self.update(db, row, **changes)
            except ValueError as e:
                self.message = (
                    f"[red]Can't save the {self.noun}:[/red] {escape(str(e))}"
                )
                return
        self.message = "[green]Saved[/green]"
        self.load()

    def handle(self, screen: tui.Screen, key: str) -> bool:
        """Act on one key; True to quit."""

        self.message = ""
        now = self.now()
        pane = self.list
        on_list = self.focus == 1
        if key in ("1", "2"):
            self.focus = int(key) - 1
        elif key in LEFT or key in RIGHT:
            self.focus = 1 - self.focus
        elif not on_list and key in (*DOWN, *UP, "g", "G", CTRL_D, CTRL_U, *ENTER):
            # The details have nothing to move through: 2 (or l) goes to the list.
            pass
        elif key in DOWN:
            pane.move(pane.cursor + 1, now)
        elif key in UP:
            pane.move(pane.cursor - 1, now)
        elif key == "g":
            pane.move(0, now)
        elif key == "G":
            pane.move(len(pane.values(now)) - 1, now)
        elif key in (CTRL_D, CTRL_U):
            _, height = screen.size()
            half = max(1, (height - 4) // 4)
            pane.move(pane.cursor + (half if key == CTRL_D else -half), now)
        elif key in ENTER:
            selected = pane.selected(now)
            if selected is not None:
                self.open(screen, selected)
        elif key in BACK:
            if not self.back() and key == tui.ESC:
                return True
        elif key == "y":
            self.copy(screen)
        elif key == "e":
            self.edit()
        elif key == "r":
            self.load()
        elif key == "q":
            return True
        else:
            self.key(screen, key)
        return False

    def show_help(self, screen: tui.Screen) -> None:
        while True:
            width, height = screen.size()
            frame = self.frame(screen.console, width, height)
            screen.draw(tui.overlay(screen.console, frame, self.help()))
            if screen.read_key() is not None:
                return

    def loop(self, screen: tui.Screen) -> None:
        """Draw, read a key, act, until the user quits."""

        self.load()
        while True:
            if monotonic() - self.loaded >= REFRESH:
                self.load()
            width, height = screen.size()
            screen.draw(self.frame(screen.console, width, height))

            data = screen.read_key(timeout=REFRESH)
            if data is None:
                continue
            for key in tui.split_keys(data):
                if key == "?":
                    self.show_help(screen)
                elif self.handle(screen, key):
                    return


def run(view: DetailView) -> None:
    """Show `view` full screen until the user quits; Ctrl-C exits with 130."""

    try:
        with open_screen() as screen:
            view.loop(screen)
    except KeyboardInterrupt:
        raise typer.Exit(130)


# The terminal, full screen; tests swap it for a fake one.
open_screen = tui.open_screen


def show_in(
    db: DBSession, view: type[DetailView], row: Any, screen: tui.Screen
) -> None:
    """
    `row`'s view on `screen`, from a browser querying with `db`: its read ends
    first, as the view writes (edit, stop) with connections of its own.
    """

    row_id = row.id
    db.commit()
    view(db.get_bind(), row_id).loop(screen)  # type: ignore[arg-type]
