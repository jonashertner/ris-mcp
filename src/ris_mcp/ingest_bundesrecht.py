"""Bundesrecht (consolidated federal law) ingester."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from .store import upsert_law


async def ingest_bundesrecht(client, conn: sqlite3.Connection) -> int:
    """Ingest consolidated federal-law metadata + text into the laws table.

    Returns the number of article rows written.
    """
    laws = await client.fetch_law_index()
    n = 0
    for law in laws:
        gesnr = law["gesetzesnummer"]
        articles = await client.fetch_law_articles(gesnr)
        for art in articles:
            row = {
                "id": f"{gesnr}:{art['paragraf']}",
                "gesetzesnummer": gesnr,
                "kurztitel": law.get("kurztitel"),
                "langtitel": law.get("langtitel"),
                "paragraf": art["paragraf"],
                "absatz": art.get("absatz"),
                "ueberschrift": art.get("ueberschrift"),
                "text": art["text"],
                "fassung_vom": art.get("fassung_vom"),
                "source_url": art.get("source_url"),
                "fetched_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
                "raw_json": json.dumps(art.get("raw", {}), ensure_ascii=False),
            }
            upsert_law(conn, row)
            n += 1
    return n
