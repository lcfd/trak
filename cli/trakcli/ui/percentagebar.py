def PercentageBar(total: int, part: int):
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
