from __future__ import annotations

import json
import re
import sqlite3

from mcp.types import TextContent, Tool

_PREFIX_RX = re.compile(r"^\s*(§|Art\.?|Artikel|Para\.?)\s*", re.IGNORECASE)


def normalise_paragraf(p: str) -> str:
    return _PREFIX_RX.sub("", p).strip()


def get_law(conn: sqlite3.Connection, *, kurztitel: str, paragraf: str) -> dict | None:
    paragraf_n = normalise_paragraf(paragraf)
    row = conn.execute(
        "SELECT * FROM laws WHERE LOWER(kurztitel) = LOWER(?) AND paragraf = ?",
        (kurztitel, paragraf_n),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d.pop("raw_json", None)
    return d


TOOL = Tool(
    name="get_law",
    description=(
        "Retrieve a single Austrian federal-law article (current consolidated Fassung) "
        "by short title (e.g. ABGB) and paragraph number."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "kurztitel": {"type": "string", "description": "e.g. ABGB, StGB, B-VG"},
            "paragraf": {"type": "string", "description": "e.g. '879', '§ 879', 'Art. 7'"},
        },
        "required": ["kurztitel", "paragraf"],
    },
)


async def handle(conn, arguments: dict):
    out = get_law(conn, **arguments)
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    return [TextContent(type="text", text=text)]
