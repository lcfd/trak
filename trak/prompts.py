"""
Vim-flavoured prompts, full screen: each question takes the whole terminal
(like every view, see `tui.py`), with the answers given so far above it.

Design principle for every interactive UI in trak: a vim/neovim user should
feel at home.

Lists:
- A list you can filter opens in INSERT mode: typing filters it.
  Esc switches to NORMAL mode.
- In NORMAL mode: j/k (or arrows) move, g/G jump to the first/last item,
  Ctrl-d/Ctrl-u move half a screen, `i` goes back to typing the filter and
  `/` starts a new one, Enter picks, Esc or q goes back without picking.
- A list you can't filter is always in NORMAL mode.
- A list can rank the matches of the filter (`rank`), e.g. so "sl" finds
  "sessions list"; otherwise the filter matches any part of an option.

Text inputs:
- Esc goes back without changing anything, like Esc on vim's command line.
- Ctrl-u clears the line, Ctrl-w deletes the word before the cursor.

Going back raises PromptCancelled: each caller decides what it means.
"""

from collections.abc import Callable, Sequence
from contextlib import ExitStack
from typing import Any, Literal, Self

from rich.style import Style
from rich.text import Text
from rich_toolkit.menu import Option
from typer._click.globals import get_current_context

from trak import panes, tui

ESC = tui.ESC
CTRL_A = "\x01"
CTRL_D = "\x04"
CTRL_E = "\x05"
CTRL_N = "\x0e"
CTRL_P = "\x10"
CTRL_U = "\x15"
CTRL_W = "\x17"
ENTER = ("\r", "\n")
BACKSPACE = ("\x7f", "\x08")
UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
DELETE = "\x1b[3~"
HOME = ("\x1b[H", "\x1b[1~", CTRL_A)
END = ("\x1b[F", "\x1b[4~", CTRL_E)

SELECTED = Style(bgcolor="grey23", bold=True)


class PromptCancelled(Exception):
    """The user went back (Esc or q) without answering."""


def split_escape(key: str) -> list[str]:
    """
    Split an Esc typed quickly together with the next key ("\\x1bj").

    Terminals send arrows and other special keys as "\\x1b[..." or "\\x1bO...":
    those stay whole.
    """

    if len(key) > 1 and key[0] == ESC and key[1] not in "[O":
        return [ESC, key[1:]]
    return [key]


# Scores how well a filter matches an option: None hides it, higher comes first.
Rank = Callable[[str, Option[Any]], float | None]


def option_text(option: Option[Any]) -> str:
    return str(option["name"])


class Menu:
    """A list to pick one option from: what keys do to it (no drawing)."""

    def __init__(
        self,
        label: str,
        options: list[Option[Any]],
        *,
        inline: bool = False,
        allow_filtering: bool = False,
        rank: Rank | None = None,
        button: Any = None,
        default: Any = None,
        normal: bool = False,
        render: Callable[[Option[Any]], Text] | None = None,
    ) -> None:
        self.label = label
        # How an option looks (its name, by default).
        self.render = render
        self.all_options = options
        self.inline = inline
        self.allow_filtering = allow_filtering
        self.rank = rank
        # The value drawn as a button, a blank line below the rest.
        self.button = button
        # `normal` starts a filterable list in NORMAL mode (`/` filters).
        self.mode: Literal["insert", "normal"] = (
            "insert" if allow_filtering and not normal else "normal"
        )
        self.text = ""
        self.selected = next(
            (
                i
                for i, o in enumerate(options)
                if o["value"] == default and default is not None
            ),
            0,
        )
        # Half the rows shown, for Ctrl-d/Ctrl-u; set when drawn.
        self.half = 5
        self._ranked: tuple[str, list[Option[Any]]] | None = None

    @property
    def options(self) -> list[Option[Any]]:
        """The options shown: those matching the filter, best first with `rank`."""

        if not (self.allow_filtering and self.text):
            return self.all_options
        if self._ranked is None or self._ranked[0] != self.text:
            if self.rank:
                scored = [(self.rank(self.text, o), o) for o in self.all_options]
                matches = [
                    o
                    for _, o in sorted(
                        ((s, o) for s, o in scored if s is not None),
                        key=lambda pair: -pair[0],  # type: ignore[operator]
                    )
                ]
            else:
                text = self.text.lower()
                matches = [
                    o for o in self.all_options if text in option_text(o).lower()
                ]
            self._ranked = (self.text, matches)
        return self._ranked[1]

    @property
    def value(self) -> Any:
        return self.options[self.selected]["value"]

    def _move_to(self, index: int) -> None:
        if self.options:
            self.selected = max(0, min(index, len(self.options) - 1))

    def _step(self, by: int) -> None:
        """One row down (1) or up (-1), wrapping around at the ends."""

        if self.options:
            self.selected = (self.selected + by) % len(self.options)

    def _set_text(self, text: str) -> None:
        self.text = text
        # The best match is what you want, not the one you were on.
        self.selected = 0

    def handle_key(self, key: str) -> bool:
        """Act on `key`; True when it picked the option at the cursor."""

        if key in ENTER:
            return bool(self.options)

        if key in (DOWN, CTRL_N) or (self.inline and key == RIGHT):
            self._step(1)
            return False
        if key in (UP, CTRL_P) or (self.inline and key == LEFT):
            self._step(-1)
            return False

        if self.mode == "insert":
            if key == ESC:
                self.mode = "normal"
            elif key in BACKSPACE:
                self._set_text(self.text[:-1])
            elif key == CTRL_U:
                self._set_text("")
            elif key == CTRL_W:
                kept = self.text.rstrip()
                self._set_text(kept[: kept.rfind(" ") + 1])
            elif key.isprintable() and not key.startswith(ESC):
                self._set_text(self.text + key)
            return False

        if key in (ESC, "q"):
            raise PromptCancelled
        if key in ("i", "a") and self.allow_filtering:
            self.mode = "insert"
        elif key == "/" and self.allow_filtering:
            self._set_text("")
            self.mode = "insert"
        elif key == "j" or (self.inline and key == "l"):
            self._step(1)
        elif key == "k" or (self.inline and key == "h"):
            self._step(-1)
        elif key == "g":
            self._move_to(0)
        elif key == "G":
            self._move_to(len(self.options) - 1)
        elif key == CTRL_D:
            self._move_to(self.selected + self.half)
        elif key == CTRL_U:
            self._move_to(self.selected - self.half)
        # Anything else does nothing in NORMAL mode, like in vim.
        return False

    def hints(self) -> list[tuple[str, str]]:
        if self.mode == "insert":
            return [
                ("type", "filter"),
                ("↑↓", "move"),
                ("Enter", "pick"),
                ("Esc", "normal mode"),
            ]
        moves = ("h/l", "move") if self.inline else ("j/k", "move")
        if self.button is not None:
            # A form: Enter changes the field at the cursor, or saves.
            return [moves, ("Enter", "change or save"), ("Esc", "discard")]
        pairs = [moves, ("Enter", "pick")]
        if self.allow_filtering:
            pairs.append(("/", "filter"))
        return [*pairs, ("Esc", "back")]

    def body(self, width: int, height: int, focused: bool = True) -> list[Text]:
        """
        The lines of the list, scrolled to the cursor, in `height` lines.
        Not `focused` (a form while one of its fields is asked), the cursor
        is a dim ▸.
        """

        lines: list[Text] = []
        if self.allow_filtering:
            lines.append(self.filter_line())
        options = self.options
        if not options:
            return [*lines, Text("No match.", style="dim")]
        if self.inline:
            row = Text("  ")
            for i, option in enumerate(options):
                name = f" {option_text(option)} "
                row.append(
                    name, style="bold reverse green" if i == self.selected else ""
                )
                row.append("  ")
            return [*lines, row]

        rows: list[tuple[Text, int]] = []
        for i, option in enumerate(options):
            is_button = self.button is not None and option["value"] == self.button
            if is_button and rows:
                rows.append((Text(), -1))
            name = Text(option_text(option))
            if self.render and not is_button:
                name = self.render(option)
            if is_button:
                on = i == self.selected and focused
                style = "bold reverse green" if on else "bold reverse"
                text = Text.assemble("  ", (f" {option_text(option)} ", style))
            elif i == self.selected and focused:
                text = Text.assemble(("› ", "bold green"), name, style=SELECTED)
            elif i == self.selected:
                text = Text.assemble(("▸ ", "dim"), name)
            else:
                text = Text.assemble("  ", name)
            rows.append((text, i))

        room = max(1, height - len(lines))
        self.half = max(1, room // 2)
        at = next(n for n, (_, i) in enumerate(rows) if i == self.selected)
        first = max(0, min(at - room // 2, len(rows) - room))
        shown = rows[first : first + room]
        return [*lines, *(text for text, _ in shown)]

    def filter_line(self) -> Text:
        if self.mode == "insert":
            return Text.assemble(("/", "bold cyan"), self.text, ("▏", "bold"))
        if self.text:
            return Text.assemble(("/", "dim"), (self.text, "dim"))
        return Text("/ to filter", style="dim")

    @property
    def answer(self) -> str:
        return option_text(self.options[self.selected]).strip()


class Validator:
    def validate_python(self, value: Any) -> Any: ...


class TextInput:
    """A line of text to type: what keys do to it (no drawing)."""

    def __init__(
        self,
        label: str,
        *,
        default: str | None = None,
        value: str | None = None,
        placeholder: str | None = None,
        validator: Validator | None = None,
    ) -> None:
        self.label = label
        self.default = default or ""
        self.placeholder = placeholder or ""
        self.validator = validator
        self.text = value or ""
        self.cursor = len(self.text)
        self.error = ""

    @property
    def value(self) -> str:
        return self.text or self.default

    def validate(self) -> bool:
        if self.validator is None:
            return True
        from pydantic import ValidationError

        try:
            self.validator.validate_python(self.value.strip())
        except ValidationError as e:
            self.error = e.errors()[0].get("msg", "Not valid")
            return False
        return True

    def handle_key(self, key: str) -> bool:
        """Act on `key`; True when it submitted a valid value."""

        if key in ENTER:
            return self.validate()
        self.error = ""
        if key == ESC:
            raise PromptCancelled
        if key in BACKSPACE:
            if self.cursor:
                self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
                self.cursor -= 1
        elif key == DELETE:
            self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
        elif key == LEFT:
            self.cursor = max(0, self.cursor - 1)
        elif key == RIGHT:
            self.cursor = min(len(self.text), self.cursor + 1)
        elif key in HOME:
            self.cursor = 0
        elif key in END:
            self.cursor = len(self.text)
        elif key == CTRL_U:
            self.text, self.cursor = "", 0
        elif key == CTRL_W:
            before = self.text[: self.cursor].rstrip()
            start = before.rfind(" ") + 1
            self.text = self.text[:start] + self.text[self.cursor :]
            self.cursor = start
        elif key.isprintable() and not key.startswith(ESC):
            self.text = self.text[: self.cursor] + key + self.text[self.cursor :]
            self.cursor += len(key)
        return False

    def hints(self) -> list[tuple[str, str]]:
        return [
            ("Enter", "confirm"),
            ("Esc", "back"),
            ("Ctrl-u", "clear"),
            ("Ctrl-w", "delete word"),
        ]

    def body(self, width: int, height: int) -> list[Text]:
        line = Text("› ", style="bold green")
        if self.text:
            line.append(self.text[: self.cursor])
            line.append(
                self.text[self.cursor : self.cursor + 1] or " ", style="reverse"
            )
            line.append(self.text[self.cursor + 1 :])
        else:
            line.append(" ", style="reverse")
            line.append(self.placeholder or self.default, style="dim")
        lines = [line]
        if self.default and not self.text:
            lines.append(Text(f"Enter keeps {self.default}", style="dim"))
        if self.error:
            lines.append(Text(self.error, style="bold red"))
        return lines

    @property
    def answer(self) -> str:
        return self.value


def command_title() -> str:
    """What's running, for the panel's title: "sessions edit"."""

    # Typer runs on its own copy of click: its context, not the `click` package's.
    ctx = get_current_context(silent=True)
    names = []
    while ctx is not None and ctx.parent is not None:
        names.append(ctx.info_name or "")
        ctx = ctx.parent
    return " ".join(reversed(names)) or "trak"


# Below this width the two panes don't fit side by side: one at a time.
WIDE = 96

# What a question is: a list, a line of text, or a picker (`pickers.py`).
Question = Any


class ScreenPrompter:
    """
    Asks questions full screen, laid out like the home: `with ScreenPrompter()
    as prompter:`.

        ┌[1] sessions create──┐┌[2] Start─────────────────────┐
        │Name     Landing page││‹ October 2026 ›              │
        │Project  website     ││Mo Tu We Th Fr Sa Su          │
        │▸ Start              ││ ...                          │
        └─────────────────────┘└──────────────────────────────┘

    [1] is what's being filled in: the answers given so far, or the fields of
    a form (a menu with a `button`, `forms.py`). [2] is the question; on a
    form's fields, it previews the one at the cursor (`preview`). The focused
    pane is green. Narrow terminals show the focused pane alone.
    """

    def __init__(self, title: str | None = None) -> None:
        self.title = title
        self.answers: list[tuple[str, str]] = []
        # The form being filled in (its menu of fields), and its preview.
        self.form: Menu | None = None
        self.preview: Callable[[Any], tuple[str, list[Text]]] | None = None
        self._stack = ExitStack()

    def __enter__(self) -> Self:
        self.screen = self._stack.enter_context(tui.open_screen())
        self.title = self.title or command_title()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stack.close()

    # Drawing.

    def answer_lines(self, label: str) -> list[Text]:
        """The answers so far, then the question being asked (▸)."""

        width = max((len(text) for text, _ in self.answers), default=0)
        lines = [
            Text.assemble((f"{text:<{width}}  ", "dim"), answer or "—")
            for text, answer in self.answers
        ]
        lines.append(Text.assemble(("▸ ", "bold green"), (label, "bold")))
        return lines

    def panes(
        self, question: Question, height: int
    ) -> tuple[tuple[str, list[Text]], tuple[str, list[Text]], int]:
        """[1] and [2] as (title, lines), and the focused one (0 or 1)."""

        title = self.title or "trak"
        if question is self.form:
            name, lines = ("", [])
            if self.preview is not None and question.options:
                name, lines = self.preview(question.value)
            return (question.label, question.body(0, height)), (name, lines), 0
        if self.form is not None:
            form = (self.form.label, self.form.body(0, height, focused=False))
            return form, (question.label, question.body(0, height)), 1
        return (
            (title, self.answer_lines(question.label)),
            (
                question.label,
                question.body(0, height),
            ),
            1,
        )

    def frame(self, question: Question) -> tui.Frame:
        width, height = self.screen.size()
        console = self.screen.console
        if tui.too_small(width, height):
            return tui.small_frame(console, width, height)

        wide = width >= WIDE
        top = tui.top_lines(width)
        body_height = height - len(top) - 2
        inner = body_height - 2
        (first, first_lines), (second, second_lines), focus = self.panes(
            question, inner
        )

        right = Text()
        if not wide:
            right = panes.tabs([("1", first), ("2", second or "Field")], focus)
        right.append(tui.clock())
        top.append(tui.line(tui.header(width, right), width))

        def box(index: int, title: str, lines: list[Text], box_width: int) -> tui.Frame:
            return panes.box(
                console,
                f"[{index + 1}] {title}",
                panes.fit_lines(lines, max(1, box_width - 4)),
                box_width,
                body_height,
                focused=focus == index,
            )

        if wide:
            left = max(44, width * 2 // 5)
            body = panes.side_by_side(
                [
                    box(0, first, first_lines, left),
                    box(1, second, second_lines, width - left),
                ]
            )
        elif focus == 0:
            body = box(0, first, first_lines, width)
        else:
            lines = second_lines
            if self.form is None and self.answers:
                # The answers above the question, while there's room.
                above = [*self.answer_lines(question.label)[:-1], Text()]
                if inner - len(above) >= 3:
                    lines = [*above, *second_lines]
            body = box(1, second, lines, width)
        footer = tui.hints(question.hints())
        return [*top, *body, tui.line(footer, width)]

    def run(self, question: Question) -> None:
        while True:
            self.screen.draw(self.frame(question))
            data = self.screen.read_key()
            if data is None:
                continue
            for key in tui.split_keys(data):
                if question.handle_key(key):
                    return

    # Questions.

    def ask(
        self,
        label: str,
        options: list[Option[Any]],
        inline: bool = False,
        allow_filtering: bool = False,
        rank: Rank | None = None,
        button: Any = None,
        default: Any = None,
        record: bool = True,
        normal: bool = False,
        render: Callable[[Option[Any]], Text] | None = None,
        preview: Callable[[Any], tuple[str, list[Text]]] | None = None,
        **_: Any,
    ) -> Any:
        """
        The value of the option picked. Its answer is listed above the next
        questions, unless `record` is False (see `note`).

        A menu with a `button` is a form: it stays in [1] while its fields
        are asked, until the button is picked; `preview(value)` is [2] then,
        as (title, lines).
        """

        menu = Menu(
            label,
            options,
            inline=inline,
            allow_filtering=allow_filtering,
            rank=rank,
            button=button,
            default=default,
            normal=normal,
            render=render,
        )
        if button is not None:
            self.answers = []
            self.form, self.preview = menu, preview
        try:
            self.run(menu)
        except PromptCancelled:
            if button is not None:
                self.form = None
            raise
        if button is not None and menu.value == button:
            self.form = None
        if button is None and record:
            self.answers.append((label, menu.answer))
        return menu.value

    def note(self, label: str, answer: str) -> None:
        """List an answer above the next questions, e.g. after several asks."""

        self.answers.append((label, answer))

    def input(
        self,
        title: str,
        default: str | None = None,
        value: str | None = None,
        placeholder: str | None = None,
        validator: Validator | None = None,
        picker: str | None = None,
        empty: str | None = None,
        **_: Any,
    ) -> str:
        """
        A line of text. With `picker` ("date" or "datetime") a calendar picks
        it instead (`pickers.py`), its answer as text all the same; `empty` is
        what no answer means there ("none", "now").
        """

        question: TextInput | Any
        if picker is not None:
            from trak.pickers import picker_of

            question = picker_of(
                picker,
                title,
                value=value or default or "",
                empty=empty,
                placeholder=placeholder or "",
                validator=validator,
            )
        else:
            question = TextInput(
                title,
                default=default,
                value=value,
                placeholder=placeholder,
                validator=validator,
            )
        self.run(question)
        self.answers.append((title, question.answer))
        return question.value

    def confirm(self, label: str, default: bool = True) -> bool:
        options: Sequence[Option[bool]] = [
            {"name": "Yes", "value": True},
            {"name": "No", "value": False},
        ]
        return bool(self.ask(label, list(options), inline=True, default=default))
