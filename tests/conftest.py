# tests/conftest.py
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> sqlite3.Connection:
    """Open an empty SQLite DB in tmp_path/ris.db with the canonical schema applied."""
    from ris_mcp.store import open_db

    db_path = tmp_path / "ris.db"
    conn = open_db(db_path)
    yield conn
    conn.close()
