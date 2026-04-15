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


@pytest.fixture
def bundesrecht_page1() -> dict:
    return json.loads((FIXTURES / "bundesrecht_search_page1.json").read_text())


@respx.mock
async def test_fetch_law_index_parses_fixture(bundesrecht_page1):
    empty = {
        "OgdSearchResult": {
            "OgdDocumentResults": {"OgdDocumentReference": []}
        }
    }
    route = respx.get(url__regex=r".*/Bundesrecht.*")
    route.side_effect = [
        Response(200, json=bundesrecht_page1),
        Response(200, json=empty),
    ]
    client = RisClient()
    laws = await client.fetch_law_index(page_size=10)
    assert isinstance(laws, list)
    assert laws, "expected at least one law parsed from fixture"
    first = laws[0]
    assert isinstance(first["gesetzesnummer"], str)
    assert first["gesetzesnummer"]
    # kurztitel / langtitel may be None for some docs but key must be present
    assert "kurztitel" in first
    assert "langtitel" in first


@respx.mock
async def test_fetch_law_index_respects_max_pages(bundesrecht_page1):
    route = respx.get(url__regex=r".*/Bundesrecht.*").mock(
        return_value=Response(200, json=bundesrecht_page1)
    )
    client = RisClient()
    laws = await client.fetch_law_index(page_size=10, max_pages=1)
    assert route.call_count == 1
    assert isinstance(laws, list)


@respx.mock
async def test_fetch_law_articles_extracts_paragraphs(bundesrecht_page1):
    empty = {
        "OgdSearchResult": {
            "OgdDocumentResults": {"OgdDocumentReference": []}
        }
    }
    respx.get(url__regex=r".*/Bundesrecht.*").mock(
        side_effect=[
            Response(200, json=bundesrecht_page1),
            Response(200, json=empty),
        ]
    )
    # Any HTML content URL: return a minimal HTML body.
    respx.get(url__regex=r"https://www\.ris\.bka\.gv\.at/Dokumente/.*\.html").mock(
        return_value=Response(200, text="<html><body><p>paragraph text</p></body></html>")
    )
    # XML / other data types shouldn't be fetched, but mock defensively.
    respx.get(url__regex=r"https://www\.ris\.bka\.gv\.at/Dokumente/.*").mock(
        return_value=Response(200, text="<html><body>fallback</body></html>")
    )
    client = RisClient()
    arts = await client.fetch_law_articles("10012838", max_pages=1)
    assert isinstance(arts, list)
    if arts:
        a = arts[0]
        assert "paragraf" in a and a["paragraf"]
        assert "text" in a
        assert "raw" in a
