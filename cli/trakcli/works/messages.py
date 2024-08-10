from datetime import datetime

from rich import print
from rich.padding import Padding

from trakcli.config.get_config import get_config
from trakcli.ui import PercentageBar
from trakcli.works.models import Work

from rich import print as rprint
from rich.table import Table

from trakcli.utils.messages import print_error


def print_work(
    work: Work,
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

    if not CONFIG or isinstance(CONFIG, list):
        return

    currency = CONFIG.get("currency", "M")

    # Closeness to deadline
    start = datetime.strptime(work.from_date, "%Y-%m-%dT%H:%M")
    end = datetime.strptime(work.to_date, "%Y-%m-%dT%H:%M")
    work_duration_days = (end - start).days
    today_to_deadline_days = (end - datetime.today()).days
    today_from_start_days = (datetime.today() - start).days

    # Workable hours
    today_to_deadline_days = (end - datetime.today()).days

    paid = "✅" if work.paid else "❌"

    if today_to_deadline_days < 0:
        remaininga_exceeded = (
            f"[red]Deadline exceeded: {today_to_deadline_days * -1} days[/red]\n"
        )
    else:
        remaininga_exceeded = f"Remaining: {today_to_deadline_days} days\n"

    # Header
    print(
        Padding(
            (
                "\n"
                "⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿ W O R K ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "--------------------------------------------------------------\n"
                f"[green]{work.name}[/green] [blue]({work.id})[/blue]\n"
                "---\n"
                f"Start: {start_date.strftime('%y-%m-%d')} "
                f"|| End: {end_date.strftime('%y-%m-%d')}\n"
                f"project: {project} || Paid: {paid}\n"
                "--------------------------------------------------------------\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "[blue]Used time budget:[/blue]\n"
                f"Total: {work.time} hours\n"
                f"Used: {hours} hours {minutes} minutes\n"
                f"{PercentageBar(work_time * 3600, totSeconds)}"
                "\n"
                "\n"
                "[blue]Closeness to the deadline:[/blue]\n"
                f"Total: {work_duration_days} days\n"
                # Remaining / Overtime
                f"{remaininga_exceeded}"
                f"{PercentageBar(work_duration_days, today_from_start_days)}\n"
                "\n"
                "\n"
                "[blue]Workable hours (8h/day) until deadline:[/blue]\n"
                f"{(today_to_deadline_days  *24) / 8} hours "
                f"in {today_to_deadline_days} days\n"
                "\n"
                f"[blue]Value of your work so far at {work.rate}{currency} "
                "per hour:[/blue]\n"
                f"[green]{work.rate*hours}{currency}[/green]\n"
                # "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "--------------------------------------------------------------\n"
                "⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟\n"
            ),
            (0, 2),
        )
    )


def print_project_works(works: list[Work] | None, project_id: str):
    """Print a table of works by project."""

    if works:
        works_table = Table(title=f"{project_id}'s works")

        works_table.add_column("Id", no_wrap=True)
        works_table.add_column("Name", no_wrap=True)
        works_table.add_column("Description")
        works_table.add_column("Time")
        works_table.add_column("Rate")
        works_table.add_column("From")
        works_table.add_column("To")
        works_table.add_column("Done")
        works_table.add_column("Paid")

        for w in works:
            time = w.time
            rate = w.rate

            from_date = w.from_date
            if from_date is not None:
                try:
                    from_date = datetime.fromisoformat(from_date).strftime("%Y-%m-%d")
                except ValueError:
                    rprint(
                        f"[red]Error in {w.id}'s from_date of {project_id} project.[/red]"
                    )

            to_date = w.to_date
            if to_date is not None:
                try:
                    to_date = datetime.fromisoformat(to_date).strftime("%Y-%m-%d")
                except ValueError:
                    rprint(
                        f"[red]Error in {w.id}'s to_date of {project_id} project.[/red]"
                    )

            works_table.add_row(
                w.id or "Missing id!",
                w.name or "Missing name!",
                w.description or "",
                f"{time}",
                f"{rate}",
                from_date,
                to_date,
                "✅" if w.done else "🏃",
                "✅" if w.paid else "❌",
            )

        rprint("")
        rprint(works_table)
    else:
        print_error(title="No works", text="Check your configuration.")

    return
