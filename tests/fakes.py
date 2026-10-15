from typing import Any


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


def add(db, row):
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
