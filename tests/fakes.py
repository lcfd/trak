from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.segment import Segment


class FakePrompter:
    """
    Answers prompts from a script: a menu answer picks the first option
    starting with it, an exception answer is raised.
    """

    def __init__(self, *answers: Any, confirm: bool = True):
        self.answers = list(answers)
        self.confirm_answer = confirm
        self.asked: list[str] = []
        self.defaults: dict[str, Any] = {}
        # The text inputs start with (their `value`).
        self.values: dict[str, Any] = {}
        # What `note` listed, e.g. the tags picked.
        self.notes: dict[str, str] = {}

    def ask(self, label, options, **kwargs):
        self.asked.append(label)
        self.defaults[label] = kwargs.get("default")
        name = self._next()
        return next(o["value"] for o in options if o["name"].startswith(name))

    def input(self, title, **kwargs):
        self.asked.append(title)
        self.values[title] = kwargs.get("value")
        # Like rich-toolkit's Input: an empty answer means the default.
        return self._next() or kwargs.get("default", "")

    def _next(self) -> Any:
        """The next answer; an exception answer is raised (e.g. PromptCancelled)."""

        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def confirm(self, label, default=True):
        return self.confirm_answer

    def note(self, label, answer):
        self.notes[label] = answer


def add(db, row):
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def frames(output: str) -> list[str]:
    """The full-screen frames printed in `output`, each starting with its header."""

    return [f" trak v{part}" for part in output.split(" trak v")[1:]]


class FakeScreen:
    """
    A terminal of `width` x `height` typing `keys`: a string is what the user
    typed, None a resize or a tick, ("resize", w, h) resizes it.
    """

    def __init__(self, keys, width=120, height=40):
        self.keys = list(keys)
        self.width, self.height = width, height
        self.console = Console(width=width, color_system=None)
        self.frames: list[str] = []
        self.suspensions = 0
        self.is_suspended = False

    def size(self):
        return self.width, self.height

    def draw(self, frame):
        assert len(frame) == self.height
        assert all(Segment.get_line_length(line) == self.width for line in frame)
        self.frames.append("\n".join("".join(s.text for s in line) for line in frame))

    def read_key(self, timeout=None):
        if not self.keys:
            raise AssertionError("The home wanted more keys")
        key = self.keys.pop(0)
        if isinstance(key, tuple):
            _, self.width, self.height = key
            return None
        return key

    @contextmanager
    def suspended(self):
        self.suspensions += 1
        self.is_suspended = True
        try:
            yield
        finally:
            self.is_suspended = False

    @property
    def last(self) -> str:
        return self.frames[-1]
