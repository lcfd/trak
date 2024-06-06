import json
from pathlib import Path


def init_config(p: Path) -> int:
    """Init the config file."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as db:
            json.dump(
                {"development": False, "projects": []},
                db,
                indent=2,
                separators=(",", ": "),
            )
        return 0
    except OSError:
        return 1
