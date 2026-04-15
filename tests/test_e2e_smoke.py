import os

import pytest

LIVE = os.environ.get("RIS_MCP_LIVE") == "1"


@pytest.mark.skipif(not LIVE, reason="set RIS_MCP_LIVE=1 to run")
async def test_full_loop_vfgh(tmp_path, monkeypatch):
    """Ingest 1 page of VfGH live, then search hits via the tool."""
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    from ris_mcp.client import RisClient, SearchResponse
    from ris_mcp.ingest import ingest_applikation
    from ris_mcp.store import open_db
    from ris_mcp.tools.search_decisions import search_decisions

    conn = open_db()
    async with RisClient() as client:
        # Bound the smoke test to a single page: after the first real fetch,
        # return an empty response so the paginator exits. The full ingester
        # would otherwise walk the entire VfGH corpus.
        real_search = client.search
        calls = {"n": 0}

        async def bounded_search(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return await real_search(*args, **kwargs)
            return SearchResponse(applikation="Vfgh", page=calls["n"], total=0, hits=[])

        monkeypatch.setattr(client, "search", bounded_search)
        n = await ingest_applikation(client, conn, applikation="Vfgh", page_size=10)
    assert n > 0
    hits = search_decisions(conn, query="Beschwerde", limit=5)
    assert hits
