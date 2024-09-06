"""Custom UI components"""


def PercentageBar(total: int, part: int):
    """Percentage bar component"""

    normalBlock = "===="
    coloredBlock = "[green]====[/green]"
    if total:
        partPerc = int((part * 100) / total)

        bar = ""
        for value in range(10):
            if value < int(partPerc / 10):
                bar += coloredBlock
            else:
                bar += normalBlock

        return f"{bar} {partPerc}%"

    return ""


def Card(title: str, header: str, body: str):
    """Card component"""

    len_title = len(title)
    side = 26

    # Topbar
    top_bar = "⣴"

    for _ in range(side):
        top_bar += "⣿"

    top_bar += f" {title} "

    for _ in range(side):
        top_bar += "⣿"

    top_bar += "⣦"

    # Bottombar

    bottom_bar = "⠻"

    for _ in range((side * 2) + len_title + 2):
        bottom_bar += "⣿"

    bottom_bar += "⠟"

    line = "--"
    for _ in range((side * 2) + len_title):
        line += "-"

    return (
        "\n"
        f"{top_bar}\n"
        # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"-{line}-\n"
        f"{header}"
        f"-{line}-\n"
        # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"{body}"
        # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"-{line}-\n"
        f"{bottom_bar}\n"
    )
