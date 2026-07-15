from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_db_path() -> Path:
    return project_root() / "data" / "rich.sqlite3"


def get_db_path() -> Path:
    return Path(os.environ.get("RICH_DB_PATH", default_db_path())).expanduser()


def get_data_mode() -> str:
    return os.environ.get("RICH_DATA_MODE", "auto").strip().lower()
