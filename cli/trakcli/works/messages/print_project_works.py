from datetime import datetime
from questionary import text
from rich.table import Table
from rich import print as rprint

from trakcli.utils.messages.print_error import print_error
from trakcli.works.models import Work


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
