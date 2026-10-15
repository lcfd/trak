"""
Full-screen views, lazygit style: they take the whole terminal (the alternate
screen, so the shell comes back untouched on quit) and redraw to its new size
when it's resized.

A view draws whole frames (`Frame`, one list of segments per line, exactly
the terminal's size) and reads keys with `read_key`, which also returns
(with None) on a resize or a timeout, to redraw.
"""

import os
import select
import signal
import sys
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol, Self

from rich import get_console
from rich.console import Console, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.segment import Segment, Segments
from rich.style import Style
from rich.text import Text
from rich_toolkit._getchar import getchar

from trak import config, dev_bar

ESC = "\x1b"

# Renders Text to segments: only its styles matter, not its size.
_CONSOLE = Console(color_system=None)

# One line of a frame, and a frame: the whole terminal.
Line = list[Segment]
Frame = list[Line]


class Screen(Protocol):
    console: Console
    is_suspended: bool

    def size(self) -> tuple[int, int]: ...

    def draw(self, frame: Frame) -> None: ...

    def read_key(self, timeout: float | None = None) -> str | None: ...

    def suspended(self) -> AbstractContextManager[None]: ...


def split_keys(data: str) -> list[str]:
    """
    The keys in what the terminal sent at once: single characters, and the
    escape sequences of special keys ("\\x1b[A", "\\x1b[1;5C", "\\x1bOP").
    An Esc not starting a sequence is a key of its own.
    """

    keys: list[str] = []
    i = 0
    while i < len(data):
        if data[i] == ESC and i + 1 < len(data) and data[i + 1] in "[O":
            j = i + 2
            if data[i + 1] == "[":
                # Parameters, then one final byte (a letter or ~).
                while j < len(data) and data[j] in "0123456789;?":
                    j += 1
            keys.append(data[i : j + 1])
            i = j + 1
        else:
            keys.append(data[i])
            i += 1
    return keys


def render(
    console: Console, renderable: RenderableType, width: int, height: int
) -> Frame:
    """`renderable` as exactly `height` lines of `width` cells."""

    options = console.options.update_dimensions(width, height)
    lines = console.render_lines(renderable, options, pad=True)
    lines = lines[:height]
    blank = [Segment(" " * width)]
    return lines + [blank] * (height - len(lines))


def overlay(console: Console, back: Frame, modal: RenderableType) -> Frame:
    """`modal` centered over a dimmed `back`."""

    height = len(back)
    width = Segment.get_line_length(back[0]) if back else console.width
    options = console.options.update(width=max(1, width - 4), height=None)
    front = console.render_lines(modal, options, pad=False)[:height]
    front_width = max((Segment.get_line_length(line) for line in front), default=0)
    top = (height - len(front)) // 2
    left = (width - front_width) // 2
    dim = Style(dim=True)

    frame: Frame = []
    for row, line in enumerate(back):
        line = list(Segment.apply_style(line, post_style=dim))
        if top <= row < top + len(front):
            modal_line = Segment.adjust_line_length(front[row - top], front_width)
            before, _, after = Segment.divide(line, [left, left + front_width, width])
            line = [*before, *modal_line, *after]
        frame.append(line)
    return frame


def line(text: Text, width: int, style: Style | str = "") -> Line:
    """`text` on one line of `width` cells: cut with an ellipsis, or padded."""

    text = text.copy()
    text.no_wrap = True
    text.truncate(width, overflow="ellipsis", pad=True)
    if style:
        text.stylize(style)
    # Text.render leaves out the text's own style (like the dev bar's
    # background): it goes under the spans.
    base = _CONSOLE.get_style(text.style) if text.style else None
    return list(Segment.apply_style(text.render(_CONSOLE), style=base))


def spread(left: Text, right: Text, width: int) -> Text:
    """`left` and `right` on one line, `right` flush right; `left` gives way."""

    room = width - right.cell_len - 1
    if room < 1:
        left = Text()
        room = 0
    left = left.copy()
    left.truncate(room, overflow="ellipsis", pad=True)
    return Text.assemble(left, " " if room else "", right)


def hints(pairs: Sequence[tuple[str, str]]) -> Text:
    """The footer of a view: "Enter run · / filter · q quit"."""

    text = Text(" ")
    for i, (keys, description) in enumerate(pairs):
        if i:
            text.append(" · ", style="bright_black")
        text.append(keys, style="bold cyan")
        text.append(f" {description}", style="dim")
    return text


def header(width: int, right: Text | None = None) -> Text:
    """The first line of every view: trak and its version, `right` flush right."""

    left = Text.assemble((" trak", "bold green"), (f" v{config.VERSION}", "dim"))
    return spread(left, right or Text(), width)


# Below this, views say so instead of drawing themselves squeezed.
MIN_WIDTH, MIN_HEIGHT = 30, 8


def too_small(width: int, height: int) -> bool:
    return width < MIN_WIDTH or height < MIN_HEIGHT + dev_bar.lines()


def top_lines(width: int) -> Frame:
    """The dev bar, in dev mode."""

    return [line(dev_bar.bar(width), width)] if dev_bar.lines() else []


def small_frame(console: Console, width: int, height: int) -> Frame:
    top = top_lines(width)
    message = Text("Make the terminal bigger to see trak.", style="bold")
    message.justify = "center"
    return top + render(console, message, width, max(0, height - len(top)))


def body_size(width: int, height: int) -> tuple[int, int]:
    """The room inside the panel of `page`: width, height."""

    return max(1, width - 4), max(1, height - dev_bar.lines() - 4)


def page(
    console: Console,
    width: int,
    height: int,
    *,
    title: str,
    body: RenderableType,
    footer: Text,
    subtitle: str = "",
    right: Text | None = None,
) -> Frame:
    """
    A whole view: the dev bar, the header, one panel filling the terminal
    with `body` (fit to `body_size`), and the `footer` (its keys).
    """

    if too_small(width, height):
        return small_frame(console, width, height)
    top = [*top_lines(width), line(header(width, right), width)]
    panel_height = height - len(top) - 1
    panel = Panel(
        body,
        title=f"[bold]{escape(title)}[/bold]",
        title_align="left",
        subtitle=escape(subtitle) if subtitle else None,
        subtitle_align="right",
        border_style="green",
        padding=(0, 1),
        height=panel_height,
        width=width,
    )
    return [*top, *render(console, panel, width, panel_height), line(footer, width)]


# The views open: the innermost last. A view inside another (a filter asked
# in a browser, a form after a picker) draws on the same screen.
_open: list["Screen"] = []


@contextmanager
def open_screen() -> Iterator["Screen"]:
    """
    The screen to draw on: the one already open, or the terminal taken over
    for this block (a `PlainScreen` without one, e.g. in tests).
    """

    if _open and not _open[-1].is_suspended:
        yield _open[-1]
        return
    has_terminal = sys.stdin.isatty() and sys.stdout.isatty()
    screen: Terminal | PlainScreen = Terminal() if has_terminal else PlainScreen()
    with screen:
        _open.append(screen)
        try:
            yield screen
        finally:
            _open.remove(screen)


class PlainScreen:
    """
    Without a terminal to take over (tests, pipes): each frame is printed
    below the last, and keys come from rich-toolkit's reader.
    """

    is_suspended = False

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or get_console()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def size(self) -> tuple[int, int]:
        return self.console.width, self.console.height

    def draw(self, frame: Frame) -> None:
        segments: list[Segment] = []
        for frame_line in frame:
            segments += [*frame_line, Segment.line()]
        self.console.print(Segments(segments), end="", crop=False, soft_wrap=True)

    def read_key(self, timeout: float | None = None) -> str | None:
        return getchar()

    @contextmanager
    def suspended(self) -> Iterator[None]:
        yield


class Terminal:
    """
    The real terminal, full screen: `with Terminal() as screen:` switches to
    the alternate screen and reads single keys until the block ends.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.is_suspended = False

    def __enter__(self) -> Self:
        import termios

        self._tty = None if sys.stdin.isatty() else open("/dev/tty")
        self._fd = (self._tty or sys.stdin).fileno()
        self._attrs = termios.tcgetattr(self._fd)

        # A resize (SIGWINCH) writes to this pipe, waking up `read_key`.
        self._wake_read, self._wake_write = os.pipe()
        os.set_blocking(self._wake_read, False)
        os.set_blocking(self._wake_write, False)
        self._old_wakeup = signal.set_wakeup_fd(self._wake_write)
        self._old_winch = signal.signal(signal.SIGWINCH, lambda *_: None)

        self._enter()
        return self

    def __exit__(self, *_: object) -> None:
        if not self.is_suspended:
            self._leave()
        signal.signal(signal.SIGWINCH, self._old_winch)
        signal.set_wakeup_fd(self._old_wakeup)
        os.close(self._wake_read)
        os.close(self._wake_write)
        if self._tty is not None:
            self._tty.close()

    def _enter(self) -> None:
        import termios
        import tty

        # Like rich-toolkit's getchar: no echo, no line buffering, and Ctrl-C
        # arrives as a key (`read_key` turns it into KeyboardInterrupt).
        raw = termios.tcgetattr(self._fd)
        raw[tty.LFLAG] &= ~(
            termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG
        )
        raw[tty.IFLAG] &= ~(
            termios.IXON | termios.IXOFF | termios.ICRNL | termios.INLCR | termios.IGNCR
        )
        raw[tty.CC][termios.VMIN] = 1
        raw[tty.CC][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSANOW, raw)
        self.console.set_alt_screen(True)
        self.console.show_cursor(False)
        self.is_suspended = False

    def _leave(self) -> None:
        import termios

        self.console.show_cursor(True)
        self.console.set_alt_screen(False)
        termios.tcsetattr(self._fd, termios.TCSANOW, self._attrs)
        self.is_suspended = True

    @contextmanager
    def suspended(self) -> Iterator[None]:
        """Back to the normal screen for a while, e.g. to run a command."""

        self._leave()
        try:
            yield
        finally:
            self._enter()

    def size(self) -> tuple[int, int]:
        width, height = os.get_terminal_size(self._fd)
        return width, height

    def draw(self, frame: Frame) -> None:
        segments: list[Segment] = [Segment("\x1b[H")]
        for row, frame_line in enumerate(frame):
            if row:
                segments.append(Segment("\r\n"))
            segments += frame_line
        # Writing the last cell doesn't scroll: no newline after the last line.
        self.console.print(Segments(segments), end="", crop=False, soft_wrap=True)
        self.console.file.flush()

    def read_key(self, timeout: float | None = None) -> str | None:
        """
        What the user typed (maybe several keys: see `split_keys`), or None
        when the terminal was resized or `timeout` seconds passed.
        """

        if self.is_suspended:
            return getchar()

        ready, _, _ = select.select([self._fd, self._wake_read], [], [], timeout)
        if self._wake_read in ready:
            try:
                while os.read(self._wake_read, 512):
                    pass
            except BlockingIOError:
                pass
            return None
        if self._fd not in ready:
            return None
        data = os.read(self._fd, 4096).decode("utf-8", errors="replace")
        if "\x03" in data:
            raise KeyboardInterrupt
        return data
