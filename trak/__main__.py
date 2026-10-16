from trak import starship

# Before importing the app: a prompt can't wait for it (`trak/starship.py`).
starship.main()

from trak.config import APP_NAME  # noqa: E402
from trak.typer_app import app  # noqa: E402

app(prog_name=APP_NAME)
