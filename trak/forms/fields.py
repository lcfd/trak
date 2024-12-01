from datetime import datetime

from trak.utils.base_messages import print_error
from trak.utils.rich_toolkit import create_rich_toolkit_app


def datetime_field(title: str, value: datetime | str | None = None) -> datetime:
    rt_app = create_rich_toolkit_app()

    if isinstance(value, datetime):
        return value

    while not isinstance(value, datetime):
        question_answer = rt_app.input(title=title)

        try:
            return datetime.strptime(question_answer, "%Y-%m-%dT%H:%M")
        except Exception:
            print_error(
                text="Invalid value inserted, it should be valid date time in %Y-%m-%dT%H:%M format."
            )
