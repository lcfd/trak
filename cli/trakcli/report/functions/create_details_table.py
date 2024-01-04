from datetime import datetime, timedelta

from rich.table import Table

from trakcli.utils.format_date import format_date


def create_details_table(project, records):
    details_table = Table(title=f"Sessions for {project}")

    details_table.add_column("Start", style="green", no_wrap=True)
    details_table.add_column("End", style="orange3", no_wrap=True)
    details_table.add_column("Category", style="steel_blue1")
    details_table.add_column("Tag", style="steel_blue3")
    details_table.add_column("Hours", style="yellow", no_wrap=True)
    details_table.add_column("Billable")

    for record in records:
        record_start = record.get("start", "")
        record_end = record.get("end", "") or datetime.now().isoformat()

        h, m = 0, 0

        if record_start != "":
            start_datetime = datetime.fromisoformat(record_start)
            end_datetime = datetime.fromisoformat(record_end)

            diff = end_datetime - start_datetime

            m, _ = divmod(diff.seconds, 60)
            h, m = divmod(m, 60)

        details_table.add_row(
            format_date(record["start"]),
            format_date(record["end"]) if record["end"] != "" else "🏃 Ongoing",
            record["category"] or "---",
            record["tag"] or "---",
            f"{h}h {m}m" if record_start != "" else "",
            "✅" if record["billable"] else "",
        )

    return details_table
