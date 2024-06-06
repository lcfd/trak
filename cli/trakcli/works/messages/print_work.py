from datetime import datetime

from rich import print as rprint
from rich.padding import Padding

from trakcli.config.main import get_config
from trakcli.utils.PercentageBar import PercentageBar


def print_work(
    work,
    start_date: datetime,
    end_date: datetime,
    project: str,
    hours,
    minutes,
    work_time,
    totSeconds,
):
    """Print the details of a work"""

    CONFIG = get_config()

    currency = CONFIG["currency"] if CONFIG["currency"] else "M"

    # Closeness to deadline
    start = datetime.strptime(work.get("from_date"), "%Y-%m-%dT%H:%M")
    end = datetime.strptime(work.get("to_date"), "%Y-%m-%dT%H:%M")
    work_duration_days = (end - start).days
    today_to_deadline_days = (end - datetime.today()).days
    today_from_start_days = (datetime.today() - start).days

    # Workable hours
    today_to_deadline_days = (end - datetime.today()).days

    # Header
    rprint(
        Padding(
            (
                "\n"
                "⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿ W O R K ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "--------------------------------------------------------------\n"
                f"[green]{work['name']}[/green] [blue]({work['id']})[/blue]\n"
                "---\n"
                f"Start: {start_date.strftime('%y-%m-%d')} || End: {end_date.strftime('%y-%m-%d')}\n"
                f"project: {project}\n"
                "--------------------------------------------------------------\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "[blue]Used time budget:[/blue]\n"
                f"Total: {work['time']} hours\n"
                f"Used: {hours} hours {minutes} minutes\n"
                f"{PercentageBar(work_time * 3600, totSeconds)}"
                "\n"
                "\n"
                "[blue]Closeness to the deadline:[/blue]\n"
                f"Total: {work_duration_days} days\n"
                f"Remaining: {today_to_deadline_days} days\n"
                f"{PercentageBar(work_duration_days, today_from_start_days)}\n"
                "\n"
                "\n"
                "[blue]Workable hours (8h/day) until deadline:[/blue]\n"
                f"{(today_to_deadline_days  *24) / 8} hours in {today_to_deadline_days} days\n"
                "\n"
                f"[blue]Value of your work so far at {work['rate']}{currency} per hour:[/blue]\n"
                f"[green]{work['rate']*hours}{currency}[/green]\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "--------------------------------------------------------------\n"
                "⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟\n"
            ),
            (0, 2),
        )
    )
