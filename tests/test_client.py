import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from ris_mcp.client import RisClient, SearchHit, SearchResponse

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def vfgh_page1() -> dict:
    return json.loads((FIXTURES / "vfgh_search_page1.json").read_text())


@pytest.fixture
def bvwg_page1() -> dict:
    return json.loads((FIXTURES / "bvwg_search_page1.json").read_text())


@respx.mock
async def test_search_returns_parsed_response(vfgh_page1):
    respx.get(url__regex=r".*/Judikatur.*").mock(return_value=Response(200, json=vfgh_page1))
    client = RisClient()
    resp = await client.search(applikation="Vfgh", page=1, page_size=10)
    assert isinstance(resp, SearchResponse)
    assert resp.applikation == "Vfgh"
    assert resp.page == 1
    assert isinstance(resp.hits, list)
    if resp.hits:
        h = resp.hits[0]
        assert isinstance(h, SearchHit)
        assert h.dokument_id
        assert h.geschaeftszahl


@respx.mock
async def test_search_retries_on_5xx():
    route = respx.get(url__regex=r".*/Judikatur.*")
    route.side_effect = [
        Response(503),
        Response(503),
        Response(
            200,
            json={"OgdSearchResult": {"OgdDocumentResults": {"OgdDocumentReference": []}}},
        ),
    ]
    client = RisClient(max_retries=3, base_delay_s=0)
    resp = await client.search(applikation="Vfgh", page=1, page_size=10)
    assert resp.hits == []
    assert route.call_count == 3


@respx.mock
async def test_fetch_document_returns_text():
    respx.get(url="https://example.test/doc.html").mock(
        return_value=Response(200, text="<html><body>Hello</body></html>")
    )
    client = RisClient()
    body = await client.fetch_document("https://example.test/doc.html")
    assert "Hello" in body


@respx.mock
async def test_search_parses_non_judikatur_section(bvwg_page1):
    respx.get(url__regex=r".*/Judikatur.*").mock(return_value=Response(200, json=bvwg_page1))
    client = RisClient()
    resp = await client.search(applikation="Bvwg", page=1, page_size=10)
    assert resp.hits, "expected at least one Bvwg hit"
    h = resp.hits[0]
    assert h.dokument_id, "dokument_id must be non-empty"
    assert h.geschaeftszahl, "geschaeftszahl must be non-empty"


@respx.mock
async def test_search_uses_persistent_client_in_context(vfgh_page1):
    respx.get(url__regex=r".*/Judikatur.*").mock(return_value=Response(200, json=vfgh_page1))
    async with RisClient() as client:
        await client.search(applikation="Vfgh", page=1, page_size=10)
        await client.search(applikation="Vfgh", page=2, page_size=10)
        assert client._http is not None
    assert client._http is None


async def test_search_rejects_unsupported_page_size():
    client = RisClient()
    with pytest.raises(ValueError, match="page_size must be one of"):
        await client.search(applikation="Vfgh", page=1, page_size=33)
