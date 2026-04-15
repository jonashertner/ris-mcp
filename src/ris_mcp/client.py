"""HTTP client for the Austrian RIS Web Service v2.6 API.

Pure HTTP. Knows nothing about SQLite or MCP. The only module that talks to
the network. All response shapes that survive past this layer are pydantic
models; nothing else propagates.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from . import __version__

DEFAULT_BASE = os.environ.get("RIS_MCP_API_BASE", "https://data.bka.gv.at/ris/api/v2.6")
DEFAULT_DELAY_MS = int(os.environ.get("RIS_MCP_REQUEST_DELAY_MS", "200"))
DEFAULT_UA = f"ris-mcp/{__version__} (+https://github.com/jonashertner/ris-mcp)"

PAGE_SIZE_ENUM = {10: "Ten", 20: "Twenty", 50: "Fifty", 100: "OneHundred"}


class SearchHit(BaseModel):
    dokument_id: str = Field(..., description="RIS Dokument-ID")
    geschaeftszahl: str = ""
    entscheidungsdatum: str | None = None
    dokumenttyp: str | None = None
    norm: str | None = None
    schlagworte: str | None = None
    rechtssatz: str | None = None
    document_url: str | None = None
    aenderungsdatum: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    applikation: str
    page: int
    total: int | None = None
    hits: list[SearchHit]


class _NoopAsyncCtx:
    """Adapter that lets ``async with`` work over a borrowed httpx client
    without closing it on exit."""

    def __init__(self, c: httpx.AsyncClient) -> None:
        self._c = c

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._c

    async def __aexit__(self, *_: Any) -> bool:
        return False


@dataclass
class RisClient:
    base_url: str = DEFAULT_BASE
    delay_ms: int = DEFAULT_DELAY_MS
    max_retries: int = 5
    base_delay_s: float = 1.0
    user_agent: str = DEFAULT_UA
    timeout_s: float = 30.0
    _http: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> RisClient:
        self._http = httpx.AsyncClient(
            timeout=self.timeout_s,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def search(
        self,
        *,
        applikation: str,
        page: int = 1,
        page_size: int = 100,
        aenderungsdatum_from: str | None = None,
    ) -> SearchResponse:
        try:
            page_size_enum = PAGE_SIZE_ENUM[page_size]
        except KeyError:
            raise ValueError(
                f"page_size must be one of {sorted(PAGE_SIZE_ENUM)}; got {page_size!r}"
            ) from None
        params: dict[str, Any] = {
            "Applikation": applikation,
            "DokumenteProSeite": page_size_enum,
            "Seitennummer": page,
        }
        if aenderungsdatum_from:
            params["Aenderungsdatum"] = f">={aenderungsdatum_from}"
        data = await self._get_json(f"{self.base_url}/Judikatur", params=params)
        return self._parse_search(applikation, page, data)

    async def fetch_document(self, url: str) -> str:
        return (await self._get(url)).text

    async def fetch_law_index(
        self,
        *,
        page_size: int = 100,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Scan consolidated Bundesrecht (BrKons) and return one entry per
        distinct Gesetzesnummer with ``{gesetzesnummer, kurztitel, langtitel}``.

        The BrKons OGD endpoint returns one document per § / Artikel, so laws
        must be deduped on the client side. ``max_pages`` caps the scan for
        tests or partial refreshes; ``None`` scans until an empty page.
        """
        try:
            page_size_enum = PAGE_SIZE_ENUM[page_size]
        except KeyError:
            raise ValueError(
                f"page_size must be one of {sorted(PAGE_SIZE_ENUM)}; got {page_size!r}"
            ) from None

        seen: dict[str, dict] = {}
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                break
            params = {
                "Applikation": "BrKons",
                "DokumenteProSeite": page_size_enum,
                "Seitennummer": page,
            }
            data = await self._get_json(f"{self.base_url}/Bundesrecht", params=params)
            refs = _refs(data)
            if not refs:
                break
            for r in refs:
                br = _br_meta(r)
                if not br:
                    continue
                sub = br.get("BrKons") or {}
                gesnr = sub.get("Gesetzesnummer")
                if not gesnr:
                    continue
                if gesnr in seen:
                    continue
                seen[gesnr] = {
                    "gesetzesnummer": str(gesnr),
                    "kurztitel": (br.get("Kurztitel") or "").strip() or None,
                    "langtitel": _strip_html(br.get("Titel")),
                }
            page += 1
        return list(seen.values())

    async def fetch_law_articles(
        self,
        gesetzesnummer: str,
        *,
        page_size: int = 100,
        max_pages: int | None = None,
        fetch_text: bool = True,
    ) -> list[dict]:
        """Return one dict per paragraph / Artikel / Anlage of the given law.

        BrKons returns each paragraph as its own document. Text is not inline
        in the metadata; when ``fetch_text`` is True we follow the HTML
        ``ContentUrl`` and strip to plain text.
        """
        try:
            page_size_enum = PAGE_SIZE_ENUM[page_size]
        except KeyError:
            raise ValueError(
                f"page_size must be one of {sorted(PAGE_SIZE_ENUM)}; got {page_size!r}"
            ) from None

        out: list[dict] = []
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                break
            params = {
                "Applikation": "BrKons",
                "Gesetzesnummer": gesetzesnummer,
                "DokumenteProSeite": page_size_enum,
                "Seitennummer": page,
            }
            data = await self._get_json(f"{self.base_url}/Bundesrecht", params=params)
            refs = _refs(data)
            if not refs:
                break
            for r in refs:
                br = _br_meta(r)
                if not br:
                    continue
                sub = br.get("BrKons") or {}
                paragraf = (
                    sub.get("Paragraphnummer")
                    or sub.get("Artikelnummer")
                    or sub.get("ArtikelParagraphAnlage")
                    or ""
                )
                paragraf = str(paragraf).strip()
                if not paragraf:
                    continue
                content_url = _extract_content_url(r.get("Data") or {})
                dok_url = (
                    ((r.get("Data") or {}).get("Metadaten") or {})
                    .get("Allgemein", {})
                    .get("DokumentUrl")
                )
                text = ""
                if fetch_text and content_url:
                    try:
                        html = await self.fetch_document(content_url)
                        text = _html_to_text(html)
                    except Exception:
                        text = ""
                out.append(
                    {
                        "paragraf": paragraf,
                        "absatz": None,
                        "ueberschrift": (br.get("Kurztitel") or "").strip() or None,
                        "text": text,
                        "fassung_vom": sub.get("Inkrafttretensdatum"),
                        "source_url": dok_url or content_url,
                        "raw": r,
                    }
                )
            page += 1
        return out

    async def _get(self, url: str, *, params: dict | None = None) -> httpx.Response:
        delay = self.base_delay_s
        last: httpx.Response | None = None
        if self._http is not None:
            client_ctx: Any = _NoopAsyncCtx(self._http)
        else:
            client_ctx = httpx.AsyncClient(
                timeout=self.timeout_s,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
        async with client_ctx as c:
            for _attempt in range(1, self.max_retries + 1):
                last = await c.get(url, params=params)
                if last.status_code < 500 and last.status_code != 429:
                    if self.delay_ms:
                        await asyncio.sleep(self.delay_ms / 1000)
                    return last
                await asyncio.sleep(delay)
                delay *= 2
        if last is None:
            raise RuntimeError("no response from server")
        last.raise_for_status()

    async def _get_json(self, url: str, *, params: dict | None = None) -> dict:
        r = await self._get(url, params=params)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _parse_search(applikation: str, page: int, data: dict) -> SearchResponse:
        """Parse the RIS /Judikatur JSON response.

        Observed shape (VfGH and Bvwg, v2.6, April 2026):

            OgdSearchResult.OgdDocumentResults.Hits = {"@pageNumber","@pageSize","#text": "<total>"}
            OgdSearchResult.OgdDocumentResults.OgdDocumentReference = [
                {
                    "Data": {
                        "Metadaten": {
                            "Technisch": {"ID": "<dokument_id>", "Applikation": "Vfgh", ...},
                            "Allgemein": {"Geaendert": "YYYY-MM-DD",
                                          "DokumentUrl": "https://..."},
                            "Judikatur": {
                                "Dokumenttyp": "Rechtssatz",
                                "Geschaeftszahl": {"item": "V258/2025"} | {"item": [...]},
                                "Normen": {"item": "..." | [...]},
                                "Entscheidungsdatum": "YYYY-MM-DD",
                                "Schlagworte": "str",
                                # Source-specific sub-section may appear here
                                # (e.g. "Bvwg": {"Gericht": ..., "Entscheidungsart": ...}).
                                ...
                            },
                        },
                        "Dokumentliste": {
                            "ContentReference": {
                                "Urls": {"ContentUrl": [{"DataType":"Xml","Url":"..."}, ...]}
                            }
                        },
                    }
                },
                ...
            ]

        Defensive against sources where the inner section may be named after the
        applikation rather than "Judikatur"; falls back to any single dict-valued
        section that looks like it holds a Geschaeftszahl.
        """
        result = data.get("OgdSearchResult") or {}
        doc_results = result.get("OgdDocumentResults") or {}
        refs = doc_results.get("OgdDocumentReference") or []
        if isinstance(refs, dict):
            refs = [refs]

        total: int | None = None
        hits_meta = doc_results.get("Hits")
        if isinstance(hits_meta, dict):
            raw_total = hits_meta.get("#text") or hits_meta.get("@total")
            if raw_total is not None:
                try:
                    total = int(raw_total)
                except (TypeError, ValueError):
                    total = None

        hits: list[SearchHit] = []
        for r in refs:
            data_obj = r.get("Data") or {}
            metadaten = data_obj.get("Metadaten") or {}
            technisch = metadaten.get("Technisch") or {}
            allgemein = metadaten.get("Allgemein") or {}
            judikatur = (
                metadaten.get("Judikatur")
                or metadaten.get(applikation)
                or _find_judikatur_like(metadaten)
                or {}
            )

            gz = _item_to_str(judikatur.get("Geschaeftszahl"))
            normen = _item_to_str(judikatur.get("Normen"), sep=" | ")
            schlagworte = _item_to_str(judikatur.get("Schlagworte"), sep=" | ")
            rechtssatz = _item_to_str(judikatur.get("Rechtssatz"))

            dokument_id = technisch.get("ID") or ""

            # DokumentUrl is the human HTML landing page; prefer the XML/HTML
            # content URL from Dokumentliste when present.
            document_url = _extract_content_url(data_obj) or allgemein.get("DokumentUrl")

            hits.append(
                SearchHit(
                    dokument_id=dokument_id,
                    geschaeftszahl=gz or "",
                    entscheidungsdatum=judikatur.get("Entscheidungsdatum"),
                    dokumenttyp=judikatur.get("Dokumenttyp"),
                    norm=normen,
                    schlagworte=schlagworte,
                    rechtssatz=rechtssatz,
                    document_url=document_url,
                    aenderungsdatum=allgemein.get("Geaendert"),
                    raw=r,
                )
            )
        return SearchResponse(applikation=applikation, page=page, total=total, hits=hits)


def _find_judikatur_like(metadaten: dict) -> dict | None:
    """Return the first dict-valued metadata section that contains a
    ``Geschaeftszahl`` field, skipping known non-judikatur sections."""
    _skip = {"Technisch", "Allgemein"}
    for k, v in metadaten.items():
        if k in _skip:
            continue
        if isinstance(v, dict) and "Geschaeftszahl" in v:
            return v
    return None


def _item_to_str(v: Any, *, sep: str = " | ") -> str | None:
    """RIS wraps many scalar/list fields as ``{"item": X}`` where X is either a
    string or a list of strings. Normalise to a flat string (joined) or None.
    """
    if v is None:
        return None
    if isinstance(v, dict):
        inner = v.get("item")
        if inner is None:
            return None
        return _item_to_str(inner, sep=sep)
    if isinstance(v, list):
        parts = [_item_to_str(x, sep=sep) for x in v]
        parts = [p for p in parts if p]
        return sep.join(parts) if parts else None
    if isinstance(v, str):
        return v or None
    return str(v)


def _refs(data: dict) -> list[dict]:
    result = data.get("OgdSearchResult") or {}
    doc_results = result.get("OgdDocumentResults") or {}
    refs = doc_results.get("OgdDocumentReference") or []
    if isinstance(refs, dict):
        refs = [refs]
    return refs


def _br_meta(ref: dict) -> dict | None:
    meta = (ref.get("Data") or {}).get("Metadaten") or {}
    br = meta.get("Bundesrecht")
    return br if isinstance(br, dict) else None


def _strip_html(s: str | None) -> str | None:
    if not s:
        return None
    txt = BeautifulSoup(s, "html.parser").get_text(" ", strip=True)
    return txt or None


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def _extract_content_url(data_obj: dict) -> str | None:
    doclist = data_obj.get("Dokumentliste") or {}
    cr = doclist.get("ContentReference")
    if not cr:
        return None
    if isinstance(cr, list):
        cr = cr[0] if cr else None
    if not isinstance(cr, dict):
        return None
    urls = cr.get("Urls") or {}
    cu = urls.get("ContentUrl")
    if cu is None:
        return None
    candidates = cu if isinstance(cu, list) else [cu]
    # Prefer Html, then Xml, then first non-empty Url.
    def _pick(dt: str) -> str | None:
        for entry in candidates:
            if isinstance(entry, dict) and entry.get("DataType") == dt and entry.get("Url"):
                return entry["Url"]
        return None

    for dt in ("Html", "Xml"):
        u = _pick(dt)
        if u:
            return u
    for entry in candidates:
        if isinstance(entry, dict) and entry.get("Url"):
            return entry["Url"]
    return None
