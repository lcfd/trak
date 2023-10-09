from rich.padding import Padding


def print_with_padding(text: str, x: int = 2, y: int = 2):
    return Padding(text, (y, x))
