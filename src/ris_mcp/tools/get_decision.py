"""MCP tool: get_decision — exact lookup by stable id or Geschäftszahl."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from mcp.types import TextContent, Tool


def _split(field: str | None) -> list[str]:
    if not field:
        return []
    return [p.strip() for p in field.split("|") if p.strip()]


def get_decision(
    conn: sqlite3.Connection,
    *,
    id: str | None = None,
    geschaeftszahl: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    if not id and not geschaeftszahl:
        raise ValueError("provide id or geschaeftszahl")

    if id:
        row = conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (id,)
        ).fetchone()
        return _shape(row) if row else None

    rows = conn.execute(
        "SELECT * FROM decisions WHERE geschaeftszahl = ? ORDER BY entscheidungsdatum DESC",
        (geschaeftszahl,),
    ).fetchall()
    if not rows:
        return None
    if len(rows) == 1:
        return _shape(rows[0])
    return [_shape(r) for r in rows]


def _shape(r) -> dict[str, Any]:
    d = dict(r)
    d["norm"] = _split(d.get("norm"))
    d["schlagworte"] = _split(d.get("schlagworte"))
    d.pop("raw_json", None)
    d.pop("text_html", None)
    return d


TOOL = Tool(
    name="get_decision",
    description="Retrieve a single Austrian court decision by stable id or Geschäftszahl.",
    inputSchema={
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "geschaeftszahl": {"type": "string"},
        },
    },
)


async def handle(conn, arguments: dict):
    out = get_decision(conn, **arguments)
    return [TextContent(type="text", text=json.dumps(out, ensure_ascii=False, indent=2, default=str))]
