"""MCP tool: search_decisions — BM25 over decisions_fts with metadata filters."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from mcp.types import TextContent, Tool


def search_decisions(
    conn: sqlite3.Connection,
    *,
    query: str,
    court: str | None = None,
    applikation: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    norm: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    limit = max(1, min(int(limit), 100))

    where = ["decisions_fts MATCH ?"]
    binds: list[Any] = [query]
    if court:
        where.append("d.court = ?")
        binds.append(court)
    if applikation:
        where.append("d.applikation = ?")
        binds.append(applikation)
    if date_from:
        where.append("d.entscheidungsdatum >= ?")
        binds.append(date_from)
    if date_to:
        where.append("d.entscheidungsdatum <= ?")
        binds.append(date_to)
    if norm:
        where.append("d.norm LIKE ?")
        binds.append(f"%{norm}%")

    sql = f"""
        SELECT d.id, d.court, d.geschaeftszahl, d.entscheidungsdatum,
               snippet(decisions_fts, -1, '[', ']', '…', 12) AS snippet,
               d.source_url
        FROM decisions_fts
        JOIN decisions d ON d.rowid = decisions_fts.rowid
        WHERE {' AND '.join(where)}
        ORDER BY bm25(decisions_fts)
        LIMIT ?
    """
    binds.append(limit)
    return [dict(r) for r in conn.execute(sql, binds).fetchall()]


TOOL = Tool(
    name="search_decisions",
    description=(
        "Search Austrian court decisions by full-text query (FTS5/BM25) "
        "with optional filters (court, applikation, date range, norm)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "FTS5 MATCH expression or keywords"},
            "court": {
                "type": "string",
                "description": (
                    "Court name. Common values: OGH, OLG Wien, OLG Graz, OLG Linz, "
                    "OLG Innsbruck, LG (various), BG (various), VfGH, VwGH, BVwG, "
                    "LVwG-Bgld, LVwG-Ktn, LVwG-NÖ, LVwG-OÖ, LVwG-Sbg, LVwG-Stmk, "
                    "LVwG-Tir, LVwG-Vbg, LVwG-Wien, DSK, DSB, GBK, PVAK. "
                    "For ordinary courts (Justiz), use the specific court name "
                    "(e.g. 'OGH'), not 'Justiz'."
                ),
            },
            "applikation": {"type": "string"},
            "date_from": {"type": "string", "description": "ISO date inclusive"},
            "date_to": {"type": "string", "description": "ISO date inclusive"},
            "norm": {"type": "string", "description": "substring match on norm field"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": ["query"],
    },
)


async def handle(conn, arguments: dict):
    rows = search_decisions(conn, **arguments)
    return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False, indent=2))]
