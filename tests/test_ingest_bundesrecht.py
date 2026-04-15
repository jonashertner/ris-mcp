from unittest.mock import AsyncMock

import pytest  # noqa: F401

from ris_mcp.ingest_bundesrecht import ingest_bundesrecht


async def test_ingest_bundesrecht_writes_articles(tmp_db):
    client = AsyncMock()
    client.fetch_law_index.return_value = [
        {
            "gesetzesnummer": "10001622",
            "kurztitel": "ABGB",
            "langtitel": "Allgemeines bürgerliches Gesetzbuch",
        },
    ]
    client.fetch_law_articles.return_value = [
        {
            "paragraf": "879",
            "absatz": None,
            "ueberschrift": "Sittenwidrige Geschäfte",
            "text": "Ein Vertrag, der gegen ein gesetzliches Verbot verstößt...",
            "fassung_vom": "2024-01-01",
            "source_url": "https://www.ris.bka.gv.at/.../P879",
            "raw": {},
        },
    ]
    n = await ingest_bundesrecht(client, tmp_db)
    assert n == 1
    row = tmp_db.execute("SELECT kurztitel, paragraf FROM laws").fetchone()
    assert row["kurztitel"] == "ABGB"
    assert row["paragraf"] == "879"


async def test_ingest_bundesrecht_multiple_articles(tmp_db):
    client = AsyncMock()
    client.fetch_law_index.return_value = [
        {"gesetzesnummer": "10001622", "kurztitel": "ABGB", "langtitel": None},
    ]
    client.fetch_law_articles.return_value = [
        {"paragraf": "1", "absatz": None, "ueberschrift": None,
         "text": "Text 1", "fassung_vom": None, "source_url": None, "raw": {}},
        {"paragraf": "2", "absatz": None, "ueberschrift": None,
         "text": "Text 2", "fassung_vom": None, "source_url": None, "raw": {}},
    ]
    n = await ingest_bundesrecht(client, tmp_db)
    assert n == 2
    rows = tmp_db.execute("SELECT paragraf FROM laws ORDER BY paragraf").fetchall()
    assert [r["paragraf"] for r in rows] == ["1", "2"]
