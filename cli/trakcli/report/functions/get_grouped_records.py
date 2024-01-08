def get_grouped_records(project, records, all):
    """Get a list of records and group them by project name."""

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
