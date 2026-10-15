"""
Vim-flavoured prompts on top of rich-toolkit.

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

from collections.abc import Callable
from typing import Any, Literal

from rich.text import Text
from rich_toolkit import RichToolkit
from rich_toolkit.container import Container
from rich_toolkit.element import Element
from rich_toolkit.input import Input
from rich_toolkit.menu import Menu, Option

ESC = "\x1b"
CTRL_D = "\x04"
CTRL_U = "\x15"
CTRL_W = "\x17"


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


class VimContainer(Container):
    """A Container that cleans up its prompt when the user goes back."""

    def run(self) -> None:
        try:
            super().run()
        except PromptCancelled:
            for element in self.elements:
                element.on_cancel()
            self._refresh(done=True)
            raise


def run_element(element: Element) -> None:
    container = VimContainer(style=element.style, metadata=element.metadata)
    container.elements = [element]
    container.run()


# Scores how well a filter matches an option: None hides it, higher comes first.
Rank = Callable[[str, Option[Any]], float | None]


class VimMenu(Menu):
    def __init__(
        self,
        *args: Any,
        rank: Rank | None = None,
        button: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if button is not None:
            self._as_button(button)
        self.mode: Literal["insert", "normal"] = (
            "insert" if self.allow_filtering else "normal"
        )
        self.rank = rank
        self._ranked: tuple[str, list[Option[Any]]] | None = None

    def _as_button(self, value: Any) -> None:
        """
        Draw the option with `value` as a button, a blank line below the rest.

        Reverse video swaps the menu colours: a white button, green when the
        cursor is on it.
        """

        index = next(i for i, o in enumerate(self._options) if o["value"] == value)
        button = self._options[index]
        self._options[index] = {
            **button,
            "name": Text(f" {button['name']} ", style="bold reverse"),  # type: ignore[typeddict-item]
        }
        if index > 0:
            above = self._options[index - 1]
            self._options[index - 1] = {**above, "name": f"{above['name']}\n"}

    @property
    def result_display_name(self) -> str:
        return str(super().result_display_name).strip()

    @property
    def options(self) -> list[Option[Any]]:
        if not (self.allow_filtering and self.rank and self.text):
            return super().options
        # Read on every key and redraw: rank once per filter text.
        if self._ranked is None or self._ranked[0] != self.text:
            scored = [
                (self.rank(self.text, option), option) for option in self._options
            ]
            ranked = sorted(
                ((score, option) for score, option in scored if score is not None),
                key=lambda pair: -pair[0],
            )
            self._ranked = (self.text, [option for _, option in ranked])
        return self._ranked[1]

    @property
    def selection_count_hint(self) -> str | None:
        # rich-toolkit prints this, dimmed, after the filter text.
        if not self.allow_filtering:
            return None
        if self.mode == "insert":
            return "  Esc: normal mode"
        return "  -- NORMAL --  j/k move · i/ filter · Enter pick · q back"

    @property
    def should_show_cursor(self) -> bool:
        return self.mode == "insert"

    def _move_to(self, index: int) -> None:
        if self.options:
            self.selected = max(0, min(index, len(self.options) - 1))
            self._ensure_selection_visible()

    def _half_screen(self) -> int:
        return max(
            1, (self.get_max_visible(self.style.console) or len(self.options)) // 2
        )

    def handle_key(self, key: str) -> None:
        for part in split_escape(key):
            self._handle_one_key(part)

    def _handle_one_key(self, key: str) -> None:
        if key == self.ENTER_KEY:
            return super().handle_key(key)

        if self.mode == "insert":
            if key == ESC:
                self.mode = "normal"
                return
            text = self.text
            super().handle_key(key)
            if self.rank and self.text != text:
                # The best match is what you want, not the one you were on.
                self._move_to(0)
            return

        if key in (ESC, "q"):
            raise PromptCancelled
        if key in ("i", "a") and self.allow_filtering:
            self.mode = "insert"
        elif key == "/" and self.allow_filtering:
            self.text, self._cursor_index = "", 0
            self._reset_scroll()
            self._move_to(0)
            self.mode = "insert"
        elif key in ("j", self.DOWN_KEY) or (
            self.inline and key in ("l", self.RIGHT_KEY)
        ):
            self._update_selection("next")
        elif key in ("k", self.UP_KEY) or (self.inline and key in ("h", self.LEFT_KEY)):
            self._update_selection("prev")
        elif key == "g":
            self._move_to(0)
        elif key == "G":
            self._move_to(len(self.options) - 1)
        elif key == CTRL_D:
            self._move_to(self.selected + self._half_screen())
        elif key == CTRL_U:
            self._move_to(self.selected - self._half_screen())
        elif self.multiple and key == " ":
            self._toggle_current()
        # Anything else does nothing in NORMAL mode, like in vim.

    def ask(self) -> Any:
        run_element(self)
        if self.multiple:
            return [self._options[i]["value"] for i in sorted(self.checked)]
        return self.options[self.selected]["value"]


class VimInput(Input):
    def handle_key(self, key: str) -> None:
        for part in split_escape(key):
            if part == ESC:
                raise PromptCancelled
            if part == CTRL_U:
                self.text, self._cursor_index = "", 0
            elif part == CTRL_W:
                self._delete_word()
            else:
                super().handle_key(part)

    def _delete_word(self) -> None:
        before = self.text[: self._cursor_index].rstrip()
        start = before.rfind(" ") + 1
        self.text = self.text[:start] + self.text[self._cursor_index :]
        self._cursor_index = start

    def ask(self) -> str:
        run_element(self)
        return self.value


class VimToolkit(RichToolkit):
    """RichToolkit whose ask/confirm/input use the vim-flavoured elements."""

    def ask(
        self,
        label: str,
        options: list[Option[Any]],
        inline: bool = False,
        allow_filtering: bool = False,
        multiple: bool = False,
        rank: Rank | None = None,
        button: Any = None,
        **metadata: Any,
    ) -> Any:
        return VimMenu(
            label=label,
            options=options,
            console=self.console,
            style=self.style,
            inline=inline,
            allow_filtering=allow_filtering,
            multiple=multiple,
            rank=rank,
            button=button,
            **metadata,
        ).ask()

    def input(self, title: str, **kwargs: Any) -> str:
        return VimInput(name=title, label=title, style=self.style, **kwargs).ask()
