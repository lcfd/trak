from trakcli.database.models import Record


def get_grouped_records(
    project: str,
    records: list[Record],
) -> dict[str, list[Record]]:
    """
    Get a list of records and group them by project name.
    In other words it filters the records by project.
    """

    ALL_PROJECTS = "all"

    grouped = {}
    for record in records:
        record_project = record.project

        if record_project:
            if record_project == project or project == ALL_PROJECTS:
                if isinstance(grouped.get(record_project, False), list):
                    grouped[record_project].append(record)
                else:
                    grouped[record_project] = [record]

    return grouped
