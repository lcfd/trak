from datetime import datetime

from rich import print

from trakcli.report.annotations import ProjectData, WorksOption
from trakcli.utils.filters import filter_records
from trakcli.works.messages import print_work


def print_details_and_works(projects_data: list[ProjectData], works: WorksOption):
    """Details --details print detailed data"""

    for data in projects_data:
        # Details
        if data["details"] is not None:
            print("")
            print(data["details"])

        # Works
        project_works = data["works"]
        if project_works is not None and works is True:
            if len(project_works):
                for pw in project_works:
                    start_date_string = pw.from_date
                    end_date_string = pw.to_date
                    start_date = datetime.strptime(start_date_string, "%Y-%m-%dT%H:%M")
                    end_date = datetime.strptime(end_date_string, "%Y-%m-%dT%H:%M")

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
