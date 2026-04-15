# tests/test_ingest.py
import logging
from unittest.mock import AsyncMock

import pytest

from ris_mcp.client import SearchHit, SearchResponse
from ris_mcp.ingest import ingest_applikation


@pytest.fixture
def fake_client():
    c = AsyncMock()
    page1 = SearchResponse(applikation="Vfgh", page=1, total=2, hits=[
        SearchHit(dokument_id="d1", geschaeftszahl="G1/24",
                  entscheidungsdatum="2024-01-01", document_url="https://x.test/d1.html",
                  aenderungsdatum="2024-01-02T10:00:00",
                  raw={"Data": {"Metadaten": {"Judikatur": {"Geschaeftszahl": "G1/24"}}}}),
        SearchHit(dokument_id="d2", geschaeftszahl="G2/24",
                  entscheidungsdatum="2024-01-03", document_url="https://x.test/d2.html",
                  aenderungsdatum="2024-01-04T10:00:00",
                  raw={"Data": {"Metadaten": {"Judikatur": {"Geschaeftszahl": "G2/24"}}}}),
    ])
    page2 = SearchResponse(applikation="Vfgh", page=2, total=2, hits=[])
    c.search.side_effect = [page1, page2]
    c.fetch_document.side_effect = ["<p>full text 1</p>", "<p>full text 2</p>"]
    return c


async def test_ingest_writes_decisions(tmp_db, fake_client):
    n = await ingest_applikation(fake_client, tmp_db, applikation="Vfgh")
    assert n == 2
    rows = tmp_db.execute("SELECT id, geschaeftszahl, text FROM decisions ORDER BY id").fetchall()
    assert [r["geschaeftszahl"] for r in rows] == ["G1/24", "G2/24"]
    assert "full text" in rows[0]["text"]


async def test_ingest_advances_watermark(tmp_db, fake_client):
    await ingest_applikation(fake_client, tmp_db, applikation="Vfgh")
    state = tmp_db.execute(
        "SELECT watermark_aenderungsdatum FROM sync_state WHERE applikation='Vfgh'"
    ).fetchone()
    assert state["watermark_aenderungsdatum"] == "2024-01-04T10:00:00"


async def test_ingest_delta_passes_watermark(tmp_db):
    c = AsyncMock()
    c.search.return_value = SearchResponse(applikation="Vfgh", page=1, hits=[])
    c.fetch_document.return_value = ""
    # seed watermark
    from ris_mcp.store import set_sync_state
    set_sync_state(tmp_db, "Vfgh", watermark="2024-06-01T00:00:00", delta=True)
    await ingest_applikation(c, tmp_db, applikation="Vfgh", delta=True)
    call = c.search.call_args
    assert call.kwargs["aenderungsdatum_from"] == "2024-06-01T00:00:00"


async def test_ingest_warns_on_empty_geschaeftszahl(tmp_db, caplog):
    client = AsyncMock()
    client.search.side_effect = [
        SearchResponse(applikation="Vfgh", page=1, hits=[
            SearchHit(
                dokument_id="orphan-1", geschaeftszahl="",
                aenderungsdatum="2024-01-01T00:00:00",
            ),
        ]),
        SearchResponse(applikation="Vfgh", page=2, hits=[]),
    ]
    client.fetch_document.return_value = ""

    with caplog.at_level(logging.WARNING):
        await ingest_applikation(client, tmp_db, applikation="Vfgh")
    assert any("empty geschaeftszahl" in r.message for r in caplog.records)
