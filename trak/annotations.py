from typer import Option
from trak.callbacks import (
    main_docs_callback,
    main_issues_callback,
    main_report_bug_callback,
    main_repository_callback,
    main_version_callback,
    main_website_callback,
)

MainVersionOption = Option(
    None,
    "--version",
    "-v",
    help="Show the application's version.",
    callback=main_version_callback,
    is_eager=True,
)

MainWebsiteOption = Option(
    None,
    "--website",
    "-w",
    help="Launch the usetrak.com website.",
    callback=main_website_callback,
    is_eager=True,
)

MainRepositoryOption = Option(
    None,
    "--repository",
    "-r",
    help="Launch the trak repository.",
    callback=main_repository_callback,
    is_eager=True,
)


MainIssuesOption = Option(
    None,
    "--issues",
    "-i",
    help="Launch the trak issues page on Github.",
    callback=main_issues_callback,
    is_eager=True,
)

MainBugOption = Option(
    None,
    "--bug",
    "-b",
    help="Report a bug on Github.",
    callback=main_report_bug_callback,
    is_eager=True,
)

MainDocsOption = Option(
    None,
    "--docs",
    help="Launch the documentation website.",
    callback=main_docs_callback,
    is_eager=True,
)
