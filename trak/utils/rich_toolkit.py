from rich_toolkit import RichToolkit, RichToolkitTheme
from rich_toolkit.styles import FancyStyle


def create_rich_toolkit_app():
    """Create of a rich toolkit app."""

    theme = RichToolkitTheme(
        style=FancyStyle(),
        theme={
            "tag.title": "black on #A7E3A2",
            "tag": "white on #893AE3",
            "placeholder": "grey85",
            "text": "white",
            "selected": "green",
            "result": "grey85",
            "progress": "on #893AE3",
        },
    )
    return RichToolkit(theme=theme)


def rich_toolkit_input(title: str):
    """Create of a rich toolkit input."""
    app = create_rich_toolkit_app()
    return app.input(title=title, default="")


def get_default_value(value: int | str | list | bool):
    if isinstance(value, bool):
        return ""

    if isinstance(value, int):
        return str(value)

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return ",".join(value)
