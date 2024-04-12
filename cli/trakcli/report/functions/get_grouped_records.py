from typing import Literal


def get_grouped_records(project: str, records, all: Literal["all"]):
    """
    Get a list of records and group them by project name.
    In other words it filters the records by project.
    """

    grouped = {}
    for record in records:
        record_project = record.get("project", False)

        if record_project:
            if record_project == project or project == all:
                if isinstance(grouped.get(record_project, False), list):
                    grouped[record_project].append(record)
                else:
                    grouped[record_project] = [record]

    return grouped
