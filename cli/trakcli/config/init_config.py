import json
from pathlib import Path


def init_config(p: Path) -> int:
    """Init the config file."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as db:
            json.dump(
                {"development": False, "currency": "€"},
                db,
                indent=2,
                separators=(",", ": "),
            )
        return True
    except OSError:
        return False
