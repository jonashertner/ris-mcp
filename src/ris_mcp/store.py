"""SQLite open / schema / CRUD helpers. The only module that touches the DB."""
from __future__ import annotations

import os
import sqlite3
from importlib.resources import files
from pathlib import Path

DECISION_COLS = (
    "id", "applikation", "court", "geschaeftszahl", "entscheidungsdatum",
    "rechtssatznummer", "dokumenttyp", "norm", "schlagworte", "rechtssatz",
    "text", "text_html", "source_url", "fetched_at", "aenderungsdatum", "raw_json",
)

LAW_COLS = (
    "id", "gesetzesnummer", "kurztitel", "langtitel", "paragraf", "absatz",
    "ueberschrift", "text", "fassung_vom", "source_url", "fetched_at", "raw_json",
)


def default_db_path() -> Path:
    if env := os.environ.get("RIS_MCP_DATA_DIR"):
        return Path(env) / "ris.db"
    home = Path(os.environ.get("HOME", "."))
    return home / ".local" / "share" / "ris-mcp" / "ris.db"


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else default_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    schema = files("ris_mcp").joinpath("schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    return conn


def upsert_decision(conn: sqlite3.Connection, row: dict) -> None:
    placeholders = ", ".join(f":{c}" for c in DECISION_COLS)
    cols = ", ".join(DECISION_COLS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in DECISION_COLS if c != "id")
    conn.execute(
        f"INSERT INTO decisions ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        {c: row.get(c) for c in DECISION_COLS},
    )
    conn.commit()


def upsert_law(conn: sqlite3.Connection, row: dict) -> None:
    placeholders = ", ".join(f":{c}" for c in LAW_COLS)
    cols = ", ".join(LAW_COLS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in LAW_COLS if c != "id")
    conn.execute(
        f"INSERT INTO laws ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        {c: row.get(c) for c in LAW_COLS},
    )
    conn.commit()


def get_sync_state(conn: sqlite3.Connection, applikation: str) -> dict | None:
    r = conn.execute("SELECT * FROM sync_state WHERE applikation=?", (applikation,)).fetchone()
    return dict(r) if r else None


def set_sync_state(
    conn: sqlite3.Connection, applikation: str, *,
    watermark: str | None = None, delta: bool = False, full: bool = False,
    total: int | None = None,
) -> None:
    fields = ["applikation"]
    values: list = [applikation]
    if watermark is not None:
        fields.append("watermark_aenderungsdatum"); values.append(watermark)
    if delta:
        fields.append("last_delta_sync"); values.append("CURRENT_TIMESTAMP_PLACEHOLDER")
    if full:
        fields.append("last_full_sync"); values.append("CURRENT_TIMESTAMP_PLACEHOLDER")
    if total is not None:
        fields.append("total_docs"); values.append(total)
    # Build manually to support CURRENT_TIMESTAMP literal
    cols = ", ".join(fields)
    placeholders = ", ".join("CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP_PLACEHOLDER" else "?" for v in values)
    bind = [v for v in values if v != "CURRENT_TIMESTAMP_PLACEHOLDER"]
    updates = ", ".join(
        f"{f}=CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP_PLACEHOLDER" else f"{f}=excluded.{f}"
        for f, v in zip(fields[1:], values[1:], strict=True)
    )
    conn.execute(
        f"INSERT INTO sync_state ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(applikation) DO UPDATE SET {updates}",
        bind,
    )
    conn.commit()
