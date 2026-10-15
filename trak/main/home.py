"""
The home of a bare `trak`, lazygit style: the whole terminal, split in three
panes reachable with 1, 2, 3 (and h/l, Tab): Goals, Sessions, Actions.

    ┌[1] Goals──────┐┌[2] Sessions───┐┌[3] Actions────┐
    │website        ││Running        ││start   Start… │
    │━━━━━━━━━  31% ││● 09:12– 2h 3m ││stop    Stop…  │
    └───────────────┘└───────────────┘└───────────────┘
     Enter run · / filter · j/k move · 1-3 panes · ? help · q quit

It starts on Actions. Enter opens the row (shows a goal or a session, runs a
command) on the normal screen, then comes back here. Narrow terminals show one
pane at a time, with the three as tabs on top.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlmodel import Session as DBSession
from typer.core import TyperCommand

from trak import clipboard, dev_bar, panes, tui
from trak.goals.display import (
    days_text,
    describe_goal,
    pace_text,
    progress_bar,
    to_go_text,
    tracked_text,
)
from trak.goals.models import Goal
from trak.goals.services import Progress, goal_progress, upcoming_goals
from trak.panes import (
    BACKSPACE,
    CTRL_D,
    CTRL_U,
    CTRL_W,
    DOWN,
    ENTER,
    LEFT,
    RIGHT,
    UP,
    Item,
    Pane,
    day_label,
    heading,
)
from trak.sessions.display import (
    describe_session,
    elapsed,
    format_duration,
    labels_text,
    session_line,
)
from trak.sessions.models import Session
from trak.sessions.services import get_active_sessions, list_sessions, stop_session

PANE_KEYS = {"1": 0, "2": 1, "3": 2}

# Below this width the panes don't fit side by side: one at a time.
WIDE = 96
# How many past sessions the Sessions pane lists.
RECENT_SESSIONS = 200
# Reload the data this often (seconds), so running times move.
REFRESH = 30

# Commands that are full-screen views: they end when the user quits them, so
# there's nothing to read afterwards, no "Press any key".
VIEWS = {"list", "report"}
FULL_SCREEN_COMMANDS = {"sessions show", "goals show", "projects show"}
HELP = "help"
QUIT = "quit"


def is_view(path: str) -> bool:
    return path.split()[-1] in VIEWS or path in FULL_SCREEN_COMMANDS


class GoalsPane(Pane):
    key, title = "1", "Goals"
    empty = "No upcoming goals.\n\n[dim]Press [bold]n[/bold] to set one.[/dim]"
    hints = (
        ("Enter", "show"),
        ("e", "edit"),
        ("y", "copy goal id"),
        ("n", "new goal"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.goals: list[tuple[Goal, str, Progress]] = []

    def load(self, db: DBSession, now: datetime) -> None:
        self.goals = [
            (goal, describe_goal(db, goal), goal_progress(db, goal, now=now))
            for goal in upcoming_goals(db, on=now.astimezone().date())
        ]

    def items(self, width: int, now: datetime) -> list[Item]:
        items = []
        for goal, name, progress in self.goals:
            lines = [
                Text(name, style="bold green"),
                progress_bar(progress, width),
                Text.from_markup(
                    f"{escape(tracked_text(progress))} [dim]·[/dim] "
                    f"{to_go_text(progress)}"
                ),
                Text.from_markup(
                    f"{days_text(progress)} [dim]· by {goal.deadline:%a %d %b}[/dim]"
                ),
            ]
            pace = pace_text(progress)
            if pace:
                lines.append(Text.from_markup(pace))
            if items:
                items.append(Item([Text()]))
            items.append(Item(lines, goal.id))
        return items


class SessionsPane(Pane):
    key, title = "2", "Sessions"
    empty = "No sessions yet.\n\n[dim]Press [bold]n[/bold] to start one.[/dim]"
    hints = (
        ("Enter", "show"),
        ("e", "edit"),
        ("s", "stop"),
        ("y", "copy session id"),
        ("n", "start"),
    )

    def __init__(self) -> None:
        super().__init__()
        # (session, what it is, its category and tag)
        self.running: list[tuple[Session, str, str]] = []
        self.recent: list[tuple[Session, str, str]] = []

    def load(self, db: DBSession, now: datetime) -> None:
        def describe(sessions: list[Session]) -> list[tuple[Session, str, str]]:
            return [(s, describe_session(db, s), labels_text(db, s)) for s in sessions]

        self.running = describe(get_active_sessions(db))
        recent, _ = list_sessions(db, limit=RECENT_SESSIONS)
        self.recent = describe([s for s in recent if not s.active])

    def items(self, width: int, now: datetime) -> list[Item]:
        items: list[Item] = []
        if self.running:
            items.append(heading(f"Running ({len(self.running)})", "bold green"))
            items += [
                Item([session_line(s, n, now, labels)], s.id)
                for s, n, labels in self.running
            ]
        today = now.astimezone().date()
        day = None
        for session, name, labels in self.recent:
            started = session.start.astimezone().date()
            if started != day:
                day = started
                if items:
                    items.append(Item([Text()]))
                items.append(heading(day_label(day, today)))
            items.append(Item([session_line(session, name, now, labels)], session.id))
        return items

    def is_running(self, session_id: int) -> bool:
        return any(s.id == session_id for s, _, _ in self.running)


class ActionsPane(Pane):
    key, title = "3", "Actions"
    hints = (("Enter", "run"), ("/", "filter"), ("y", "copy command"))

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        # (path, description), with help and quit at the end.
        self.rows = rows
        self.filter = ""
        self.filtering = False

    @property
    def empty(self) -> str:  # type: ignore[override]
        return "[dim]No command matches.[/dim]"

    def matches(self) -> list[tuple[str, str]]:
        from trak.main.menu import command_score

        if not self.filter.strip():
            return self.rows
        scored = [(command_score(self.filter, *row), row) for row in self.rows]
        ranked = sorted(
            ((s, row) for s, row in scored if s is not None), key=lambda p: -p[0]
        )
        return [row for _, row in ranked]

    def items(self, width: int, now: datetime) -> list[Item]:
        rows = self.matches()
        name_width = max((len(path) for path, _ in self.rows), default=0)
        return [
            Item(
                [Text.assemble((f"{path:<{name_width}}  ", "bold"), (text, "dim"))],
                path,
            )
            for path, text in rows
        ]

    def subtitle(self, selectable: int) -> str:
        if self.filtering:
            return f"/{self.filter}▏"
        if self.filter:
            return f"/{self.filter} · {super().subtitle(selectable)}"
        return super().subtitle(selectable)


@dataclass
class Home:
    ctx: typer.Context
    commands: dict[str, TyperCommand]
    actions: list[tuple[str, str]]
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    focus: int = 2
    message: str = ""
    panes: list[Pane] = field(init=False)

    def __post_init__(self) -> None:
        self.goals = GoalsPane()
        self.sessions = SessionsPane()
        self.actions_pane = ActionsPane(self.actions)
        self.panes = [self.goals, self.sessions, self.actions_pane]
        self.loaded = 0.0

    # Data.

    def load(self) -> None:
        now = self.now()
        with DBSession(self.ctx.obj["DB_ENGINE"]) as db:
            self.goals.load(db, now)
            self.sessions.load(db, now)
        self.loaded = monotonic()

    @property
    def pane(self) -> Pane:
        return self.panes[self.focus]

    def selectable(self, pane: Pane, now: datetime) -> int:
        return sum(1 for item in pane.items(80, now) if item.value is not None)

    def clamp(self, now: datetime) -> None:
        for pane in self.panes:
            count = self.selectable(pane, now)
            pane.cursor = max(0, min(pane.cursor, count - 1))

    # Drawing.

    def hints(self) -> list[tuple[str, str]]:
        if self.focus == 2 and self.actions_pane.filtering:
            return [("Enter", "run"), ("Esc", "stop filtering"), ("↑↓", "move")]
        return [
            *self.pane.hints,
            ("j/k", "move"),
            ("1-3", "panes"),
            ("?", "help"),
            ("q", "quit"),
        ]

    def footer(self, width: int) -> Text:
        if self.message:
            return Text.from_markup(f" {self.message}")
        return tui.hints(self.hints())

    def header(self, width: int, wide: bool, now: datetime) -> Text:
        """trak, the panes as tabs when they don't fit side by side, the time."""

        right = Text()
        if not wide:
            right = panes.tabs([(p.key, p.title) for p in self.panes], self.focus)
        running = len(self.sessions.running)
        if running and wide:
            right.append(f"● {running} running  ", style="bold green")
        right.append(f"{now.astimezone():%a %d %b %H:%M} ", style="dim")
        return tui.header(width, right)

    def panel(
        self, console: Console, pane: Pane, width: int, height: int, now: datetime
    ) -> tui.Frame:
        return panes.render(
            console, pane, width, height, now, focused=pane is self.pane
        )

    def frame(self, console: Console, width: int, height: int) -> tui.Frame:
        now = self.now()
        if tui.too_small(width, height):
            return tui.small_frame(console, width, height)
        top = tui.top_lines(width)

        wide = width >= WIDE
        top.append(tui.line(self.header(width, wide, now), width))
        body_height = height - len(top) - 1

        if wide:
            widths = [width // 3] * 3
            widths[2] += width - sum(widths)
            columns = [
                self.panel(console, pane, w, body_height, now)
                for pane, w in zip(self.panes, widths)
            ]
            body = panes.side_by_side(columns)
        else:
            body = self.panel(console, self.pane, width, body_height, now)

        return [*top, *body, tui.line(self.footer(width), width)]

    def help(self) -> Panel:
        grid = Table.grid(padding=(0, 3))
        grid.add_column(style="bold cyan", justify="right")
        grid.add_column()
        rows: Sequence[tuple[str, str]] = [
            ("1  2  3", "Goals, Sessions, Actions"),
            ("h  l  Tab", "Previous, next pane"),
            ("j  k  ↓  ↑", "Next, previous row"),
            ("g  G", "First, last row"),
            ("Ctrl-d  Ctrl-u", "Half a pane down, up"),
            ("Enter", "Show the goal or session, run the action"),
            ("e", "Edit the goal or session"),
            ("n", "New goal (Goals), start a session (Sessions)"),
            ("s", "Stop the running session (Sessions)"),
            ("y", "Copy the goal's or session's id, the action's command"),
            ("/  i", "Filter the actions, resume the filter"),
            ("Esc", "Stop filtering, then clear the filter"),
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

    # Keys.

    def move(self, to: int) -> None:
        count = self.selectable(self.pane, self.now())
        self.pane.cursor = max(0, min(to, count - 1))

    def half(self, screen: tui.Screen) -> int:
        _, height = screen.size()
        return max(1, (height - 4) // 4)

    def filter_key(self, key: str) -> None:
        pane = self.actions_pane
        if key == tui.ESC:
            pane.filtering = False
        elif key in BACKSPACE:
            pane.filter = pane.filter[:-1]
        elif key == CTRL_U:
            pane.filter = ""
        elif key == CTRL_W:
            pane.filter = pane.filter.rstrip()
            pane.filter = pane.filter[: pane.filter.rfind(" ") + 1]
        elif key in ("\x1b[B", "\x0e"):
            self.move(pane.cursor + 1)
            return
        elif key in ("\x1b[A", "\x10"):
            self.move(pane.cursor - 1)
            return
        elif key.isprintable() and not key.startswith(tui.ESC):
            pane.filter += key
        else:
            return
        # The best match is what you want, not the row you were on.
        pane.cursor = 0

    def open(self, screen: tui.Screen, key: str) -> bool:
        """What Enter, e, n and s do on the focused pane; True to quit."""

        now = self.now()
        pane = self.pane
        value = pane.selected(now)
        entity = {0: "goals", 1: "sessions"}.get(self.focus)

        if pane is self.actions_pane:
            if key not in ENTER or value is None:
                return False
            # Back to the whole list, on the command picked: Enter runs it again.
            pane.filter, pane.filtering = "", False
            pane.cursor = [path for path, _ in pane.rows].index(value)
            if value == QUIT:
                return True
            if value == HELP:
                return self.run(screen, HELP)
            return self.run(screen, value)

        if key == "n":
            return self.run(screen, "goals create" if self.focus == 0 else "start")
        if value is None:
            return False
        if key in ENTER:
            return self.run(screen, f"{entity} show", [str(value)])
        if key == "e":
            return self.run(screen, f"{entity} edit", [str(value)])
        if key == "s" and pane is self.sessions:
            self.stop(value)
        return False

    def copy(self, screen: tui.Screen) -> None:
        """The id of the goal or session selected; `trak <path>` of an action."""

        value = self.pane.selected(self.now())
        if value is None:
            return
        what = {0: "goal", 1: "session"}.get(self.focus, "command")
        if self.pane is self.actions_pane:
            if value in (HELP, QUIT):
                return
            value = f"trak {value}"
        self.message = clipboard.copied(str(value), screen.console, what=what)

    def stop(self, session_id: int) -> None:
        if not self.sessions.is_running(session_id):
            self.message = "[yellow]That session isn't running.[/yellow]"
            return
        with DBSession(self.ctx.obj["DB_ENGINE"]) as db:
            session = db.get(Session, session_id)
            assert session is not None
            stop_session(db, session)
            name = describe_session(db, session)
            took = format_duration(elapsed(session))
        self.message = (
            f"[green]Stopped[/green] [bold]{escape(name)}[/bold] [dim]· {took}[/dim]"
        )
        self.load()

    def run(self, screen: tui.Screen, path: str, args: Sequence[str] = ()) -> bool:
        """
        Run a command on the normal screen, then wait for a key before coming
        back (not after a full-screen view). True when that key is q: quit.
        """

        with screen.suspended():
            dev_bar.clear(Console())
            if path == HELP:
                typer.echo(self.ctx.get_help())
            else:
                run_command(self.ctx, self.commands[path], path, args)
            quit_ = False
            if not is_view(path):
                Console().print(
                    "\n[dim]Press any key to go back to trak, "
                    "[bold]q[/bold] to quit.[/dim]"
                )
                key = None
                while key is None:
                    key = screen.read_key()
                quit_ = key == "q"
        self.load()
        return quit_

    def handle(self, screen: tui.Screen, key: str) -> bool:
        """Act on one key; True to quit."""

        self.message = ""
        if self.focus == 2 and self.actions_pane.filtering:
            if key in ENTER:
                return self.open(screen, key)
            self.filter_key(key)
            return False

        pane = self.pane
        if key in PANE_KEYS:
            self.focus = PANE_KEYS[key]
        elif key in LEFT:
            self.focus = (self.focus - 1) % len(self.panes)
        elif key in RIGHT:
            self.focus = (self.focus + 1) % len(self.panes)
        elif key in DOWN:
            self.move(pane.cursor + 1)
        elif key in UP:
            self.move(pane.cursor - 1)
        elif key == "g":
            self.move(0)
        elif key == "G":
            self.move(self.selectable(pane, self.now()) - 1)
        elif key == CTRL_D:
            self.move(pane.cursor + self.half(screen))
        elif key == CTRL_U:
            self.move(pane.cursor - self.half(screen))
        elif key == "/" and pane is self.actions_pane:
            self.actions_pane.filter, self.actions_pane.filtering = "", True
            pane.cursor = 0
        elif key in ("i", "a") and pane is self.actions_pane:
            self.actions_pane.filtering = True
        elif key == tui.ESC and pane is self.actions_pane:
            self.actions_pane.filter, pane.cursor = "", 0
        elif key == "y":
            self.copy(screen)
        elif key == "r":
            self.load()
        elif key == "q":
            return True
        elif key in (*ENTER, "e", "n", "s"):
            return self.open(screen, key)
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
            self.clamp(self.now())
            width, height = screen.size()
            screen.draw(self.frame(screen.console, width, height))

            data = screen.read_key(timeout=REFRESH)
            # A resize, or time to refresh: draw again.
            if data is None:
                continue
            for key in tui.split_keys(data):
                if key == "?" and not self.actions_pane.filtering:
                    self.show_help(screen)
                elif self.handle(screen, key):
                    return


def run_command(
    ctx: typer.Context, command: TyperCommand, path: str, args: Sequence[str]
) -> None:
    """Run `command` under `ctx` as if typed with `args`; its errors stay here."""

    try:
        with command.make_context(path, list(args), parent=ctx) as sub_ctx:
            command.invoke(sub_ctx)
    except (typer.Exit, typer.Abort, SystemExit, KeyboardInterrupt):
        # It said why already (an error panel, "Cancelled"), or Ctrl-C.
        pass
    except typer.TyperException as error:
        # A usage error, like a bad option value.
        show = getattr(error, "show", None)
        if show is not None:
            show()
        else:
            typer.echo(str(error), err=True)
