import typer

app = typer.Typer()


@app.command()
def start(project: str):
    print(f"Start project {project}")


@app.command()
def stop(project: str):
    print(f"Start project {project}")


@app.command()
def report(project: str, when: str = typer.Option(default="month")):
    print(f"Report project {project} — {when}")


if __name__ == "__main__":
    app()
