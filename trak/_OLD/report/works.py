from datetime import datetime


from trak._OLD.database import get_db_content, get_project_works
from trak.report.annotations import ProjectIdOption, WorkIdOption
from trak.utils.get_grouped_records import get_grouped_records
from trak.utils.base_messages import print_error
from trak.utils.filters import filter_records
from trak.utils.projects import project_exists, projects_picker
from trak.utils.works import works_picker
from trak.works.messages import print_work


def report_works(
    project_id: ProjectIdOption = None,
    work_id: WorkIdOption = None,
):
    """
    Show reports for your works.
    """

    if isinstance(project_id, str) and not project_exists(project_id):
        print_error(text=f'The project "{project_id}" doesn\'t exist.')
        return

    # Get project id
    project_id = projects_picker(project_id=project_id, archived=False, all=True)
    if not project_id:
        return

    works_picker_result = works_picker(project_id=project_id, work_id=work_id)
    if not works_picker_result:
        return

    work_id, _ = works_picker_result

    # Get database content
    db_content = get_db_content()
    if db_content is None:
        print_error(
            title="Corrupted database",
            text="Check your database, you may have some broken records.",
        )
        return

    # Group data
    grouped = get_grouped_records(project_id, db_content)

    # Accumulators

    projects_data: list = []

    for g in grouped:
        # Only billable records are considered.
        records = filter_records(
            records=grouped[g],
            billable=True,
        )

        project_data = {
            "project": g,
            "works": [],
            "records": records,
        }

        if len(records):
            project_works = get_project_works(g)
            if project_works is not None:
                project_data["works"] = [project_works[work_id]]

        projects_data.append(project_data)

    for data in projects_data:
        project_works = data["works"]

        if project_works is not None and len(project_works):
            for pw in project_works:
                start_date = datetime.strptime(pw.from_date, "%Y-%m-%dT%H:%M")
                end_date = datetime.strptime(pw.to_date, "%Y-%m-%dT%H:%M")

                filtered_records = filter_records(
                    records=data.get("records"), start=start_date, end=end_date
                )

                acc_seconds = 0

                for record in filtered_records:
                    record_start = record.start
                    record_end = record.end

                    if record_start != "" and record_end != "":
                        start_datetime = datetime.fromisoformat(record_start)
                        end_datetime = datetime.fromisoformat(record_end)

                        diff = end_datetime - start_datetime

                        acc_seconds = acc_seconds + diff.seconds

                        m, _ = divmod(diff.seconds, 60)
                        h, m = divmod(m, 60)

                m, _ = divmod(acc_seconds, 60)
                h, m = divmod(m, 60)

                print_work(
                    work=pw,
                    start_date=start_date,
                    end_date=end_date,
                    project=data["project"],
                    hours=h,
                    minutes=m,
                    work_time=pw.time,
                    totSeconds=acc_seconds,
                )
