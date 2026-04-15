"""Coverage/stats report for the local corpus. Emits JSON consumed by
docs/stats.json and the Pages site.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any

SCHEMA_VERSION = 1


def generate_coverage(conn: sqlite3.Connection) -> dict[str, Any]:
    total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    total_laws = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]

    by_court_rows = conn.execute(
        "SELECT court, COUNT(*) FROM decisions GROUP BY court ORDER BY court"
    ).fetchall()
    by_court = {row[0]: row[1] for row in by_court_rows}

    span = conn.execute(
        "SELECT MIN(entscheidungsdatum), MAX(entscheidungsdatum) FROM decisions"
    ).fetchone()
    last_aenderung = conn.execute(
        "SELECT MAX(aenderungsdatum) FROM decisions"
    ).fetchone()[0]

    return {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_decisions": total_decisions,
        "total_laws": total_laws,
        "decisions_by_court": by_court,
        "corpus_span": {"earliest": span[0], "latest": span[1]},
        "last_aenderungsdatum": last_aenderung,
        "schema_version": SCHEMA_VERSION,
    }
