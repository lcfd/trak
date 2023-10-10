from pathlib import Path

#
# Paths
#


TRAK_FOLDER = Path.home() / ".trak"

DB_FILE_PATH = TRAK_FOLDER / "db.json"
CONFIG_FILE_PATH = TRAK_FOLDER / "config.json"


#
# Configuration helpers
#


def init_config(p: Path) -> int:
    """Create the to-do database."""

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            f.write("{}")
        return 0
    except OSError:
        return 1
