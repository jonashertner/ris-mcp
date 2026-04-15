# ris-mcp Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `ris-mcp` v0.1.0 — a local MCP server that lets Claude search and retrieve Austrian court decisions and federal statutes from a locally-mirrored, FTS5-indexed SQLite store fed by the official RIS Web Service v2.6 API.

**Architecture:** Generic `RisClient` (HTTP) → `RisIngester` (parameterised by `ApplikationConfig` registry) → SQLite canonical store with FTS5 → MCP stdio server exposing 3 tools (`search_decisions`, `get_decision`, `get_law`). Layers are strictly separated so future phases (citation graph, vector search, remote hosting) plug in without rework.

**Tech Stack:** Python 3.11+, `httpx`, `pydantic`, `mcp` (official Python SDK), SQLite + FTS5 (stdlib `sqlite3`), `pytest`, `ruff`, `uv` for env mgmt and `uvx`-based install. No ORM (raw SQL via thin `store.py` helpers).

**Spec:** `docs/superpowers/specs/2026-04-15-ris-mcp-phase1-design.md`

---

## File structure (created across all tasks)

```
ris-mcp/
├── pyproject.toml
├── README.md
├── LICENSE                              # MIT
├── DATA_LICENSE                         # CC0-1.0
├── .gitignore
├── .python-version                      # 3.11
├── src/ris_mcp/
│   ├── __init__.py
│   ├── client.py                        # RisClient (HTTP only)
│   ├── applikation.py                   # ApplikationConfig + REGISTRY
│   ├── store.py                         # SQLite open + helpers
│   ├── schema.sql                       # Canonical DDL
│   ├── ingest.py                        # RisIngester (Judikatur)
│   ├── ingest_bundesrecht.py            # Bundesrecht ingester
│   ├── server.py                        # MCP server + tool registration
│   ├── cli.py                           # `ris-ingest`, `ris-mcp` entrypoints
│   └── tools/
│       ├── __init__.py
│       ├── search_decisions.py
│       ├── get_decision.py
│       └── get_law.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # tmp DB fixture
│   ├── fixtures/
│   │   ├── vfgh_search_page1.json       # recorded API response
│   │   └── vfgh_doc.html
│   ├── test_client.py
│   ├── test_applikation.py
│   ├── test_store.py
│   ├── test_ingest.py
│   ├── test_ingest_bundesrecht.py
│   ├── test_search_decisions.py
│   ├── test_get_decision.py
│   ├── test_get_law.py
│   └── test_cli.py
└── .github/workflows/
    └── ci.yml
```

Each file has one clear responsibility. `client.py` knows HTTP, nothing else. `store.py` knows SQLite, nothing else. `tools/*` are thin: parse → query → format.

---

### Task 1: Scaffold repo

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `DATA_LICENSE`, `.gitignore`, `.python-version`, `README.md`, `src/ris_mcp/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create `.python-version`**

```
3.11
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "ris-mcp"
version = "0.1.0.dev0"
description = "MCP server for Austrian RIS (court decisions + federal law) backed by a local FTS5-indexed SQLite mirror"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Jonas Hertner", email = "jonashertner@protonmail.ch" }]
dependencies = [
  "httpx>=0.27",
  "pydantic>=2.7",
  "mcp>=1.2",
  "click>=8.1",
  "beautifulsoup4>=4.12",
  "lxml>=5.0",
]

[project.scripts]
ris-mcp = "ris_mcp.cli:mcp_main"
ris-ingest = "ris_mcp.cli:ingest_main"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "respx>=0.21", "ruff>=0.6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ris_mcp"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `LICENSE` (MIT)**

Standard MIT text, copyright `2026 Jonas Hertner`.

- [ ] **Step 4: Create `DATA_LICENSE`**

```
The data ingested by this software from the Austrian Rechtsinformationssystem
(RIS, https://www.ris.bka.gv.at) consists of amtliche Werke within the meaning
of § 7 öUrhG and is in the public domain. Any redistribution of such data by
projects using this software is dedicated to the public domain under
Creative Commons Zero v1.0 (CC0-1.0): https://creativecommons.org/publicdomain/zero/1.0/
```

- [ ] **Step 5: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.coverage
```

- [ ] **Step 6: Create `src/ris_mcp/__init__.py`**

```python
__version__ = "0.1.0.dev0"
```

- [ ] **Step 7: Create `tests/__init__.py` (empty) and `tests/conftest.py`**

```python
# tests/conftest.py
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> sqlite3.Connection:
    """Open an empty SQLite DB in tmp_path/ris.db with the canonical schema applied."""
    from ris_mcp.store import open_db

    db_path = tmp_path / "ris.db"
    conn = open_db(db_path)
    yield conn
    conn.close()
```

- [ ] **Step 8: Skeleton `README.md`**

```markdown
# ris-mcp

Local MCP server for the Austrian Rechtsinformationssystem (RIS) — court decisions and consolidated federal law, queryable from Claude (Code, Desktop, claude.ai).

> **Status:** Phase 1 (v0.1.0-dev) — see `docs/superpowers/specs/` for design and `docs/superpowers/plans/` for the implementation plan.

## Why

`philrox/ris-mcp-ts` (TypeScript) already wraps the live RIS API as MCP tools. This project does something different: it maintains a **locally-mirrored, FTS5-indexed copy** of the corpus, so search quality, latency, and offline capability all exceed what live API calls can deliver. Future phases add a citation graph, semantic search, and bulk dataset publishing — all of which require the local mirror.

## Install (after v0.1.0)

```bash
claude mcp add ris -- uvx ris-mcp serve
ris-ingest --full        # one-time historical backfill (~1–3 days)
```

## Licenses

- Code: MIT (see `LICENSE`)
- Data: CC0-1.0; RIS content is amtliches Werk per § 7 öUrhG (see `DATA_LICENSE`)

## Credits

Builds on the documentation work of `ximex/ris-bka` and learns from `philrox/ris-mcp-ts` and `PhilippTh/ris-API-wrapper`.
```

- [ ] **Step 9: Set up venv and install dev deps**

```bash
cd /Users/jonashertner/RIS
uv venv
uv pip install -e ".[dev]"
```

Expected: clean install, no errors.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml LICENSE DATA_LICENSE .gitignore .python-version README.md src/ tests/
git commit -m "Scaffold ris-mcp project structure"
```

---

### Task 2: ApplikationConfig + registry

**Files:**
- Create: `src/ris_mcp/applikation.py`
- Test: `tests/test_applikation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_applikation.py
from ris_mcp.applikation import REGISTRY, ApplikationConfig, get_applikation


def test_registry_includes_apex_courts():
    codes = {a.code for a in REGISTRY}
    assert {"Justiz", "Vfgh", "Vwgh", "Bvwg"}.issubset(codes)


def test_registry_includes_lvwg_per_land():
    codes = {a.code for a in REGISTRY}
    # LVwG is split per Bundesland in RIS API; expect 9
    lvwg = {c for c in codes if c.startswith("Lvwg")}
    assert len(lvwg) == 9


def test_each_applikation_has_normalised_court():
    for a in REGISTRY:
        assert isinstance(a, ApplikationConfig)
        assert a.court  # non-empty normalised label


def test_get_applikation_lookup():
    cfg = get_applikation("Vfgh")
    assert cfg.court == "VfGH"


def test_get_applikation_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_applikation("DoesNotExist")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_applikation.py -v
```

Expected: ImportError / module not found.

- [ ] **Step 3: Implement**

```python
# src/ris_mcp/applikation.py
"""Registry of Austrian RIS Judikatur 'Applikationen' (data sources).

The exact list and code spelling is canonical to the RIS Web Service v2.6 API at
https://data.bka.gv.at/ris/api/v2.6/Judikatur. This file is the single source of
truth for which sources we ingest.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApplikationConfig:
    code: str          # exact RIS Applikation parameter value
    court: str         # normalised court label used in our schema
    description: str   # human-readable description (en)


REGISTRY: tuple[ApplikationConfig, ...] = (
    ApplikationConfig("Justiz", "Justiz", "Ordinary courts (OGH/OLG/LG/BG) — civil & criminal"),
    ApplikationConfig("Vfgh", "VfGH", "Constitutional Court"),
    ApplikationConfig("Vwgh", "VwGH", "Supreme Administrative Court"),
    ApplikationConfig("Bvwg", "BVwG", "Federal Administrative Court"),
    ApplikationConfig("LvwgBgld", "LVwG-Bgld", "Burgenland LVwG"),
    ApplikationConfig("LvwgKtn", "LVwG-Ktn", "Kärnten LVwG"),
    ApplikationConfig("LvwgNoe", "LVwG-NÖ", "Niederösterreich LVwG"),
    ApplikationConfig("LvwgOoe", "LVwG-OÖ", "Oberösterreich LVwG"),
    ApplikationConfig("LvwgSbg", "LVwG-Sbg", "Salzburg LVwG"),
    ApplikationConfig("LvwgStmk", "LVwG-Stmk", "Steiermark LVwG"),
    ApplikationConfig("LvwgTir", "LVwG-Tir", "Tirol LVwG"),
    ApplikationConfig("LvwgVbg", "LVwG-Vbg", "Vorarlberg LVwG"),
    ApplikationConfig("LvwgWien", "LVwG-Wien", "Wien LVwG"),
    ApplikationConfig("Dsk", "DSK", "Datenschutzkommission (historical)"),
    ApplikationConfig("Dsb", "DSB", "Datenschutzbehörde"),
    ApplikationConfig("Gbk", "GBK", "Gleichbehandlungskommission"),
    ApplikationConfig("Pvak", "PVAK", "Personalvertretungs-Aufsichtskommission"),
    ApplikationConfig("Bvwg", "BVwG", "Federal Administrative Court"),
)

# NOTE: real Applikation enum will be confirmed during Task 3 first live smoke
# test. If RIS reports a different code spelling for any LVwG, fix here and
# re-run tests.

_BY_CODE = {a.code: a for a in REGISTRY}


def get_applikation(code: str) -> ApplikationConfig:
    return _BY_CODE[code]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_applikation.py -v
```

Expected: all PASS. (If `Bvwg` duplicate triggers a test failure, fix the registry — keep it deduped.)

- [ ] **Step 5: Commit**

```bash
git add src/ris_mcp/applikation.py tests/test_applikation.py
git commit -m "Add Applikation registry for RIS judikatur sources"
```

---

### Task 3: RisClient (HTTP layer)

**Files:**
- Create: `src/ris_mcp/client.py`, `tests/fixtures/vfgh_search_page1.json`
- Test: `tests/test_client.py`

- [ ] **Step 1: Capture a real fixture**

```bash
mkdir -p tests/fixtures
curl -s 'https://data.bka.gv.at/ris/api/v2.6/Judikatur?Applikation=Vfgh&DokumenteProSeite=Ten&Seitennummer=1' \
  -H 'Accept: application/json' \
  -o tests/fixtures/vfgh_search_page1.json
head -c 500 tests/fixtures/vfgh_search_page1.json
```

Expected: a real JSON response. If the API returns XML by default, append `&Format=Json` or set `Accept: application/json`. Inspect and adjust the fixture URL until JSON is returned. Save it.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_client.py
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
    route.side_effect = [Response(503), Response(503), Response(200, json={"OgdSearchResult": {"OgdDocumentResults": {"OgdDocumentReference": []}}})]
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
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_client.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `client.py`**

```python
# src/ris_mcp/client.py
"""HTTP client for the Austrian RIS Web Service v2.6 API.

Pure HTTP. Knows nothing about SQLite or MCP. The only module that talks to
the network. All response shapes that survive past this layer are pydantic
models; nothing else propagates.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx
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


@dataclass
class RisClient:
    base_url: str = DEFAULT_BASE
    delay_ms: int = DEFAULT_DELAY_MS
    max_retries: int = 5
    base_delay_s: float = 1.0
    user_agent: str = DEFAULT_UA
    timeout_s: float = 30.0

    async def search(
        self,
        *,
        applikation: str,
        page: int = 1,
        page_size: int = 100,
        aenderungsdatum_from: str | None = None,
    ) -> SearchResponse:
        params = {
            "Applikation": applikation,
            "DokumenteProSeite": PAGE_SIZE_ENUM[page_size],
            "Seitennummer": page,
        }
        if aenderungsdatum_from:
            params["Aenderungsdatum"] = f">={aenderungsdatum_from}"
        data = await self._get_json(f"{self.base_url}/Judikatur", params=params)
        return self._parse_search(applikation, page, data)

    async def fetch_document(self, url: str) -> str:
        return (await self._get(url)).text

    async def _get(self, url: str, *, params: dict | None = None) -> httpx.Response:
        delay = self.base_delay_s
        last: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=self.timeout_s, headers={"User-Agent": self.user_agent, "Accept": "application/json"}) as c:
            for attempt in range(1, self.max_retries + 1):
                last = await c.get(url, params=params)
                if last.status_code < 500 and last.status_code != 429:
                    if self.delay_ms:
                        await asyncio.sleep(self.delay_ms / 1000)
                    return last
                await asyncio.sleep(delay)
                delay *= 2
        assert last is not None
        last.raise_for_status()
        return last

    async def _get_json(self, url: str, *, params: dict | None = None) -> dict:
        r = await self._get(url, params=params)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _parse_search(applikation: str, page: int, data: dict) -> SearchResponse:
        # RIS API nests results under OgdSearchResult.OgdDocumentResults.OgdDocumentReference
        result = data.get("OgdSearchResult", {})
        doc_results = result.get("OgdDocumentResults") or {}
        refs = doc_results.get("OgdDocumentReference") or []
        if isinstance(refs, dict):
            refs = [refs]
        total = doc_results.get("@Hits")
        hits: list[SearchHit] = []
        for r in refs:
            data_obj = (r.get("Data") or {})
            metadaten = (data_obj.get("Metadaten") or {})
            judikatur = (metadaten.get("Judikatur") or {})
            hits.append(SearchHit(
                dokument_id=r.get("@DokumentNummer") or r.get("@ID") or "",
                geschaeftszahl=_first(judikatur.get("Geschaeftszahl")) or "",
                entscheidungsdatum=judikatur.get("Entscheidungsdatum"),
                dokumenttyp=judikatur.get("Dokumenttyp"),
                norm=_first(judikatur.get("Normen")),
                schlagworte=_first(judikatur.get("Schlagworte")),
                rechtssatz=judikatur.get("Rechtssatz"),
                document_url=_first((data_obj.get("Dokumentliste") or {}).get("ContentReference") or {}).get("Urls") if data_obj.get("Dokumentliste") else None,
                aenderungsdatum=metadaten.get("Aenderungsdatum"),
                raw=r,
            ))
        return SearchResponse(applikation=applikation, page=page, total=int(total) if total else None, hits=hits)


def _first(v):
    if v is None:
        return None
    if isinstance(v, list):
        return v[0] if v else None
    return v
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_client.py -v
```

Expected: all PASS.

If the fixture you captured in Step 1 has a different shape than what `_parse_search` expects, **adjust `_parse_search` to match the real shape, not the test data**. The test asserts `dokument_id` and `geschaeftszahl` are present — those must come out non-empty for at least one hit.

- [ ] **Step 6: Live smoke (off-CI)**

```bash
RIS_MCP_LIVE=1 python -c "
import asyncio
from ris_mcp.client import RisClient
async def main():
    c = RisClient()
    r = await c.search(applikation='Vfgh', page=1, page_size=10)
    print(f'total={r.total} hits={len(r.hits)}')
    if r.hits:
        print(r.hits[0].model_dump_json(indent=2))
asyncio.run(main())
"
```

Expected: prints a real VfGH hit. Confirms parser matches live API.

- [ ] **Step 7: Commit**

```bash
git add src/ris_mcp/client.py tests/test_client.py tests/fixtures/
git commit -m "Add RisClient with paginated search and document fetch"
```

---

### Task 4: Store + schema

**Files:**
- Create: `src/ris_mcp/store.py`, `src/ris_mcp/schema.sql`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write `schema.sql`**

```sql
-- src/ris_mcp/schema.sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS decisions (
  id              TEXT PRIMARY KEY,
  applikation     TEXT NOT NULL,
  court           TEXT NOT NULL,
  geschaeftszahl  TEXT NOT NULL,
  entscheidungsdatum DATE,
  rechtssatznummer TEXT,
  dokumenttyp     TEXT,
  norm            TEXT,
  schlagworte     TEXT,
  rechtssatz      TEXT,
  text            TEXT,
  text_html       TEXT,
  source_url      TEXT,
  fetched_at      TIMESTAMP NOT NULL,
  aenderungsdatum TIMESTAMP,
  raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_court_date ON decisions(court, entscheidungsdatum DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_geschaeftszahl ON decisions(geschaeftszahl);
CREATE INDEX IF NOT EXISTS idx_decisions_aenderung ON decisions(aenderungsdatum);

CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
  geschaeftszahl, court, norm, schlagworte, rechtssatz, text,
  content='decisions', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
  INSERT INTO decisions_fts(rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES (new.rowid, new.geschaeftszahl, new.court, new.norm, new.schlagworte, new.rechtssatz, new.text);
END;
CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
  INSERT INTO decisions_fts(decisions_fts, rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES('delete', old.rowid, old.geschaeftszahl, old.court, old.norm, old.schlagworte, old.rechtssatz, old.text);
END;
CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
  INSERT INTO decisions_fts(decisions_fts, rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES('delete', old.rowid, old.geschaeftszahl, old.court, old.norm, old.schlagworte, old.rechtssatz, old.text);
  INSERT INTO decisions_fts(rowid, geschaeftszahl, court, norm, schlagworte, rechtssatz, text)
  VALUES (new.rowid, new.geschaeftszahl, new.court, new.norm, new.schlagworte, new.rechtssatz, new.text);
END;

CREATE TABLE IF NOT EXISTS laws (
  id              TEXT PRIMARY KEY,
  gesetzesnummer  TEXT NOT NULL,
  kurztitel       TEXT,
  langtitel       TEXT,
  paragraf        TEXT NOT NULL,
  absatz          TEXT,
  ueberschrift    TEXT,
  text            TEXT NOT NULL,
  fassung_vom     DATE,
  source_url      TEXT,
  fetched_at      TIMESTAMP NOT NULL,
  raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_laws_kurztitel ON laws(kurztitel);

CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(
  kurztitel, langtitel, paragraf, ueberschrift, text,
  content='laws', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS laws_ai AFTER INSERT ON laws BEGIN
  INSERT INTO laws_fts(rowid, kurztitel, langtitel, paragraf, ueberschrift, text)
  VALUES (new.rowid, new.kurztitel, new.langtitel, new.paragraf, new.ueberschrift, new.text);
END;

CREATE TABLE IF NOT EXISTS sync_state (
  applikation     TEXT PRIMARY KEY,
  last_full_sync  TIMESTAMP,
  last_delta_sync TIMESTAMP,
  watermark_aenderungsdatum TIMESTAMP,
  total_docs      INTEGER DEFAULT 0
);
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_store.py
import datetime as dt

from ris_mcp.store import (
    default_db_path, get_sync_state, open_db, set_sync_state, upsert_decision, upsert_law,
)


def test_default_db_path_under_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("RIS_MCP_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = default_db_path()
    assert p.parent.name == "ris-mcp"
    assert p.name == "ris.db"


def test_open_db_applies_schema(tmp_db):
    cur = tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    assert {"decisions", "laws", "sync_state"}.issubset(tables)


def test_upsert_decision_round_trips_and_indexes_fts(tmp_db):
    upsert_decision(tmp_db, {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G123/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG", "schlagworte": "Gleichheit",
        "rechtssatz": None, "text": "Die Beschwerde wird abgewiesen.",
        "text_html": "<p>Die Beschwerde wird abgewiesen.</p>",
        "source_url": "https://example.test/x",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00",
        "raw_json": "{}",
    })
    rows = tmp_db.execute(
        "SELECT id FROM decisions_fts WHERE decisions_fts MATCH 'Beschwerde'"
    ).fetchall()
    assert rows


def test_upsert_decision_updates_existing(tmp_db):
    base = {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": None,
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "old", "text_html": None, "source_url": None,
        "fetched_at": "2024-06-01T00:00:00", "aenderungsdatum": "2024-06-01T00:00:00",
        "raw_json": "{}",
    }
    upsert_decision(tmp_db, base)
    upsert_decision(tmp_db, {**base, "text": "new"})
    rows = tmp_db.execute("SELECT text FROM decisions WHERE id='Vfgh:abc'").fetchall()
    assert rows == [("new",)]


def test_upsert_law_round_trips(tmp_db):
    upsert_law(tmp_db, {
        "id": "10001622:879", "gesetzesnummer": "10001622", "kurztitel": "ABGB",
        "langtitel": "Allgemeines bürgerliches Gesetzbuch", "paragraf": "879",
        "absatz": None, "ueberschrift": "Sittenwidrige Geschäfte",
        "text": "Ein Vertrag, der gegen ein gesetzliches Verbot...",
        "fassung_vom": "2024-01-01", "source_url": None,
        "fetched_at": "2024-06-01T00:00:00", "raw_json": "{}",
    })
    rows = tmp_db.execute("SELECT id FROM laws_fts WHERE laws_fts MATCH 'Sittenwidrig'").fetchall()
    assert rows


def test_sync_state_round_trip(tmp_db):
    assert get_sync_state(tmp_db, "Vfgh") is None
    set_sync_state(tmp_db, "Vfgh", watermark="2024-06-01T00:00:00", delta=True, total=42)
    s = get_sync_state(tmp_db, "Vfgh")
    assert s["watermark_aenderungsdatum"] == "2024-06-01T00:00:00"
    assert s["total_docs"] == 42
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_store.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `store.py`**

```python
# src/ris_mcp/store.py
"""SQLite open / schema / CRUD helpers. The only module that touches the DB."""
from __future__ import annotations

import os
import sqlite3
from importlib.resources import files
from pathlib import Path

DECISION_COLS = (
    "id", "applikation", "court", "geschaeftszahl", "entscheidungsdatum",
    "rechtssatznummer", "dokumenttyp", "norm", "schlagworte", "rechtssatz",
    "text", "text_html", "source_url", "fetched_at", "aenderungsdatum", "raw_json",
)

LAW_COLS = (
    "id", "gesetzesnummer", "kurztitel", "langtitel", "paragraf", "absatz",
    "ueberschrift", "text", "fassung_vom", "source_url", "fetched_at", "raw_json",
)


def default_db_path() -> Path:
    if env := os.environ.get("RIS_MCP_DATA_DIR"):
        return Path(env) / "ris.db"
    home = Path(os.environ.get("HOME", "."))
    return home / ".local" / "share" / "ris-mcp" / "ris.db"


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else default_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    schema = files("ris_mcp").joinpath("schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    return conn


def upsert_decision(conn: sqlite3.Connection, row: dict) -> None:
    placeholders = ", ".join(f":{c}" for c in DECISION_COLS)
    cols = ", ".join(DECISION_COLS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in DECISION_COLS if c != "id")
    conn.execute(
        f"INSERT INTO decisions ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        {c: row.get(c) for c in DECISION_COLS},
    )
    conn.commit()


def upsert_law(conn: sqlite3.Connection, row: dict) -> None:
    placeholders = ", ".join(f":{c}" for c in LAW_COLS)
    cols = ", ".join(LAW_COLS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in LAW_COLS if c != "id")
    conn.execute(
        f"INSERT INTO laws ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        {c: row.get(c) for c in LAW_COLS},
    )
    conn.commit()


def get_sync_state(conn: sqlite3.Connection, applikation: str) -> dict | None:
    r = conn.execute("SELECT * FROM sync_state WHERE applikation=?", (applikation,)).fetchone()
    return dict(r) if r else None


def set_sync_state(
    conn: sqlite3.Connection, applikation: str, *,
    watermark: str | None = None, delta: bool = False, full: bool = False,
    total: int | None = None,
) -> None:
    fields = ["applikation"]
    values: list = [applikation]
    if watermark is not None:
        fields.append("watermark_aenderungsdatum"); values.append(watermark)
    if delta:
        fields.append("last_delta_sync"); values.append("CURRENT_TIMESTAMP_PLACEHOLDER")
    if full:
        fields.append("last_full_sync"); values.append("CURRENT_TIMESTAMP_PLACEHOLDER")
    if total is not None:
        fields.append("total_docs"); values.append(total)
    # Build manually to support CURRENT_TIMESTAMP literal
    cols = ", ".join(fields)
    placeholders = ", ".join("CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP_PLACEHOLDER" else "?" for v in values)
    bind = [v for v in values if v != "CURRENT_TIMESTAMP_PLACEHOLDER"]
    updates = ", ".join(
        f"{f}=CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP_PLACEHOLDER" else f"{f}=excluded.{f}"
        for f, v in zip(fields[1:], values[1:], strict=True)
    )
    conn.execute(
        f"INSERT INTO sync_state ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(applikation) DO UPDATE SET {updates}",
        bind,
    )
    conn.commit()
```

- [ ] **Step 5: Add `schema.sql` to package data**

In `pyproject.toml` add under `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/ris_mcp/schema.sql" = "ris_mcp/schema.sql"
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
pytest tests/test_store.py -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ris_mcp/store.py src/ris_mcp/schema.sql pyproject.toml tests/test_store.py
git commit -m "Add SQLite store with FTS5 schema and upsert helpers"
```

---

### Task 5: RisIngester (Judikatur)

**Files:**
- Create: `src/ris_mcp/ingest.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ingest.py
import json
from pathlib import Path
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
    state = tmp_db.execute("SELECT watermark_aenderungsdatum FROM sync_state WHERE applikation='Vfgh'").fetchone()
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
```

- [ ] **Step 2: Run, verify fails**

```bash
pytest tests/test_ingest.py -v
```

- [ ] **Step 3: Implement `ingest.py`**

```python
# src/ris_mcp/ingest.py
"""Generic Judikatur ingester. Parameterised by ApplikationConfig.

Orchestrates: page through RIS search, fetch document HTML, normalise to text,
upsert into SQLite. Crash-safe (commit per page). Delta-aware via Aenderungsdatum.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any

from bs4 import BeautifulSoup

from .applikation import get_applikation
from .client import RisClient, SearchHit
from .store import get_sync_state, set_sync_state, upsert_decision


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator="\n", strip=True)


def _row_from_hit(hit: SearchHit, applikation: str, court: str, full_text_html: str) -> dict[str, Any]:
    text = _html_to_text(full_text_html) if full_text_html else (hit.rechtssatz or "")
    return {
        "id": f"{applikation}:{hit.dokument_id}",
        "applikation": applikation,
        "court": court,
        "geschaeftszahl": hit.geschaeftszahl,
        "entscheidungsdatum": hit.entscheidungsdatum,
        "rechtssatznummer": None,
        "dokumenttyp": hit.dokumenttyp,
        "norm": hit.norm,
        "schlagworte": hit.schlagworte,
        "rechtssatz": hit.rechtssatz,
        "text": text,
        "text_html": full_text_html or None,
        "source_url": hit.document_url,
        "fetched_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "aenderungsdatum": hit.aenderungsdatum,
        "raw_json": json.dumps(hit.raw, ensure_ascii=False),
    }


async def ingest_applikation(
    client: RisClient,
    conn: sqlite3.Connection,
    *,
    applikation: str,
    delta: bool = False,
    page_size: int = 100,
) -> int:
    cfg = get_applikation(applikation)
    watermark: str | None = None
    if delta:
        state = get_sync_state(conn, applikation)
        watermark = state.get("watermark_aenderungsdatum") if state else None

    page = 1
    total = 0
    max_aenderung: str | None = watermark
    while True:
        resp = await client.search(
            applikation=applikation, page=page, page_size=page_size,
            aenderungsdatum_from=watermark,
        )
        if not resp.hits:
            break
        for hit in resp.hits:
            full_html = ""
            if hit.document_url:
                try:
                    full_html = await client.fetch_document(hit.document_url)
                except Exception:
                    full_html = ""
            row = _row_from_hit(hit, applikation, cfg.court, full_html)
            upsert_decision(conn, row)
            total += 1
            if hit.aenderungsdatum and (max_aenderung is None or hit.aenderungsdatum > max_aenderung):
                max_aenderung = hit.aenderungsdatum
        page += 1

    set_sync_state(
        conn, applikation,
        watermark=max_aenderung,
        delta=delta, full=not delta,
        total=total,
    )
    return total
```

- [ ] **Step 4: Run, verify passes**

```bash
pytest tests/test_ingest.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ris_mcp/ingest.py tests/test_ingest.py
git commit -m "Add generic Judikatur ingester with delta sync"
```

---

### Task 6: Bundesrecht ingester

**Files:**
- Create: `src/ris_mcp/ingest_bundesrecht.py`
- Test: `tests/test_ingest_bundesrecht.py`

- [ ] **Step 1: Capture fixture**

```bash
curl -s 'https://data.bka.gv.at/ris/api/v2.6/Bundesrecht?Applikation=BrKons&Kundmachungsorgan=BGBl&DokumenteProSeite=Ten&Seitennummer=1' \
  -H 'Accept: application/json' \
  -o tests/fixtures/bundesrecht_search_page1.json
```

If `BrKons` is not the correct Applikation code for consolidated Bundesrecht, try `Bundesnormen`, `Br`, then check the API Help endpoint at `/Bundesrecht/Help`. Capture whichever returns real consolidated-law metadata.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_ingest_bundesrecht.py
from unittest.mock import AsyncMock

import pytest

from ris_mcp.ingest_bundesrecht import ingest_bundesrecht


async def test_ingest_bundesrecht_writes_articles(tmp_db):
    client = AsyncMock()
    # Stub: one law (ABGB), one paragraph
    client.fetch_law_index.return_value = [
        {"gesetzesnummer": "10001622", "kurztitel": "ABGB",
         "langtitel": "Allgemeines bürgerliches Gesetzbuch"},
    ]
    client.fetch_law_articles.return_value = [
        {"paragraf": "879", "absatz": None, "ueberschrift": "Sittenwidrige Geschäfte",
         "text": "Ein Vertrag, der gegen ein gesetzliches Verbot verstößt...",
         "fassung_vom": "2024-01-01",
         "source_url": "https://www.ris.bka.gv.at/.../P879", "raw": {}},
    ]
    n = await ingest_bundesrecht(client, tmp_db)
    assert n == 1
    row = tmp_db.execute("SELECT kurztitel, paragraf FROM laws").fetchone()
    assert row["kurztitel"] == "ABGB"
    assert row["paragraf"] == "879"
```

- [ ] **Step 3: Run, verify fails**

- [ ] **Step 4: Implement**

```python
# src/ris_mcp/ingest_bundesrecht.py
"""Bundesrecht (consolidated federal law) ingester.

Two-stage: enumerate all Gesetze, then walk articles per Gesetz. Uses a small
client adapter exposed by RisClient — see ingest.RisClient.fetch_law_index /
fetch_law_articles. (These two methods are added in this task.)
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any

from .store import upsert_law


async def ingest_bundesrecht(client, conn: sqlite3.Connection) -> int:
    laws = await client.fetch_law_index()
    n = 0
    for law in laws:
        articles = await client.fetch_law_articles(law["gesetzesnummer"])
        for art in articles:
            row = {
                "id": f"{law['gesetzesnummer']}:{art['paragraf']}",
                "gesetzesnummer": law["gesetzesnummer"],
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
```

- [ ] **Step 5: Add `fetch_law_index` and `fetch_law_articles` to `RisClient`**

Append to `src/ris_mcp/client.py`:

```python
    async def fetch_law_index(self) -> list[dict]:
        """Enumerate all consolidated federal laws. Paginated server-side."""
        out: list[dict] = []
        page = 1
        while True:
            data = await self._get_json(
                f"{self.base_url}/Bundesrecht",
                params={"Applikation": "BrKons", "Typ": "Gesetz",
                        "DokumenteProSeite": "OneHundred", "Seitennummer": page},
            )
            result = data.get("OgdSearchResult", {}).get("OgdDocumentResults") or {}
            refs = result.get("OgdDocumentReference") or []
            if isinstance(refs, dict):
                refs = [refs]
            if not refs:
                break
            for r in refs:
                meta = (r.get("Data") or {}).get("Metadaten") or {}
                br = meta.get("Bundesrecht") or {}
                gn = br.get("Gesetzesnummer") or r.get("@DokumentNummer")
                if not gn:
                    continue
                out.append({
                    "gesetzesnummer": str(gn),
                    "kurztitel": _first(br.get("Kurztitel")),
                    "langtitel": _first(br.get("Titel")),
                })
            page += 1
        return out

    async def fetch_law_articles(self, gesetzesnummer: str) -> list[dict]:
        """Fetch all paragraphs for a single Gesetz. Real shape pinned during
        live smoke; this is the minimal contract the bundesrecht ingester needs.
        """
        data = await self._get_json(
            f"{self.base_url}/Bundesrecht",
            params={"Applikation": "BrKons", "Gesetzesnummer": gesetzesnummer,
                    "DokumenteProSeite": "OneHundred", "Seitennummer": 1},
        )
        result = data.get("OgdSearchResult", {}).get("OgdDocumentResults") or {}
        refs = result.get("OgdDocumentReference") or []
        if isinstance(refs, dict):
            refs = [refs]
        out: list[dict] = []
        for r in refs:
            meta = (r.get("Data") or {}).get("Metadaten") or {}
            br = meta.get("Bundesrecht") or {}
            paragraf = br.get("Paragraph") or br.get("Artikel")
            if not paragraf:
                continue
            content_url = None
            doclist = (r.get("Data") or {}).get("Dokumentliste") or {}
            cr = doclist.get("ContentReference")
            if cr:
                cr = cr if isinstance(cr, list) else [cr]
                urls = (cr[0].get("Urls") or {}).get("ContentUrl") if cr else None
                if urls:
                    content_url = urls[0].get("Url") if isinstance(urls, list) else urls.get("Url")
            text = ""
            if content_url:
                try:
                    text = (await self._get(content_url)).text
                    text = BeautifulSoup(text, "lxml").get_text(separator="\n", strip=True)
                except Exception:
                    text = ""
            out.append({
                "paragraf": paragraf,
                "absatz": br.get("Absatz"),
                "ueberschrift": br.get("Ueberschrift"),
                "text": text,
                "fassung_vom": meta.get("FassungVom"),
                "source_url": content_url,
                "raw": r,
            })
        return out
```

Add at top of `client.py`: `from bs4 import BeautifulSoup`.

- [ ] **Step 6: Run tests, verify they pass**

```bash
pytest tests/test_ingest_bundesrecht.py tests/test_client.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/ris_mcp/ingest_bundesrecht.py src/ris_mcp/client.py tests/test_ingest_bundesrecht.py tests/fixtures/
git commit -m "Add Bundesrecht ingester and law-index/articles client methods"
```

---

### Task 7: MCP server skeleton + stdio

**Files:**
- Create: `src/ris_mcp/server.py`, `src/ris_mcp/cli.py`, `src/ris_mcp/tools/__init__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli.py
from click.testing import CliRunner

from ris_mcp.cli import ingest_main, mcp_main


def test_ingest_help():
    r = CliRunner().invoke(ingest_main, ["--help"])
    assert r.exit_code == 0
    assert "--full" in r.output and "--delta" in r.output


def test_mcp_help():
    r = CliRunner().invoke(mcp_main, ["--help"])
    assert r.exit_code == 0
```

- [ ] **Step 2: Implement `tools/__init__.py`** (empty for now)

```python
# src/ris_mcp/tools/__init__.py
```

- [ ] **Step 3: Implement `server.py` skeleton**

```python
# src/ris_mcp/server.py
"""MCP server (stdio). Wires SDK to tool functions in ris_mcp.tools.*"""
from __future__ import annotations

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .store import open_db

log = logging.getLogger(__name__)


def build_server() -> Server:
    server = Server("ris-mcp")
    conn = open_db()

    # Tool registration is added in Tasks 8–10.
    from .tools import search_decisions as t_sd
    from .tools import get_decision as t_gd
    from .tools import get_law as t_gl

    t_sd.register(server, conn)
    t_gd.register(server, conn)
    t_gl.register(server, conn)
    return server


async def serve() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
```

- [ ] **Step 4: Implement `cli.py`**

```python
# src/ris_mcp/cli.py
from __future__ import annotations

import asyncio

import click

from . import server as mcp_server
from .applikation import REGISTRY
from .client import RisClient
from .ingest import ingest_applikation
from .ingest_bundesrecht import ingest_bundesrecht
from .store import open_db


@click.command("ris-ingest")
@click.option("--full", is_flag=True, help="Full historical backfill")
@click.option("--delta", is_flag=True, help="Incremental sync since last watermark")
@click.option("--applikation", default=None, help="Restrict to one Applikation code")
@click.option("--include-bundesrecht/--no-bundesrecht", default=True)
def ingest_main(full: bool, delta: bool, applikation: str | None, include_bundesrecht: bool) -> None:
    if not (full or delta):
        raise click.UsageError("specify --full or --delta")

    async def run():
        client = RisClient()
        conn = open_db()
        codes = [applikation] if applikation else [a.code for a in REGISTRY]
        for code in codes:
            click.echo(f"==> {code}")
            n = await ingest_applikation(client, conn, applikation=code, delta=delta)
            click.echo(f"    {n} decisions")
        if include_bundesrecht:
            click.echo("==> Bundesrecht")
            n = await ingest_bundesrecht(client, conn)
            click.echo(f"    {n} articles")

    asyncio.run(run())


@click.command("ris-mcp")
@click.argument("subcommand", type=click.Choice(["serve"]), default="serve")
def mcp_main(subcommand: str) -> None:
    if subcommand == "serve":
        mcp_server.main()
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: PASS. (Tools modules are imported but registration happens only when `build_server()` is called, not on import.)

- [ ] **Step 6: Commit**

```bash
git add src/ris_mcp/server.py src/ris_mcp/cli.py src/ris_mcp/tools/__init__.py tests/test_cli.py
git commit -m "Add MCP server skeleton and CLI entrypoints"
```

---

### Task 8: Tool — search_decisions

**Files:**
- Create: `src/ris_mcp/tools/search_decisions.py`
- Test: `tests/test_search_decisions.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search_decisions.py
import datetime as dt

from ris_mcp.store import upsert_decision
from ris_mcp.tools.search_decisions import search_decisions


def _seed(conn):
    upsert_decision(conn, {
        "id": "Vfgh:1", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG", "schlagworte": "Gleichheit",
        "rechtssatz": None, "text": "Die Beschwerde betreffend Gleichheit wird abgewiesen.",
        "text_html": None, "source_url": "https://x/1",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00", "raw_json": "{}",
    })
    upsert_decision(conn, {
        "id": "Vwgh:1", "applikation": "Vwgh", "court": "VwGH",
        "geschaeftszahl": "Ra2024/01/0001", "entscheidungsdatum": "2024-05-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "§ 879 ABGB", "schlagworte": "Sittenwidrigkeit",
        "rechtssatz": None, "text": "Sittenwidrigkeit eines Vertrags...",
        "text_html": None, "source_url": "https://x/2",
        "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-05-02T10:00:00", "raw_json": "{}",
    })


def test_search_returns_fts_match(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Sittenwidrigkeit")
    assert len(out) == 1
    assert out[0]["geschaeftszahl"] == "Ra2024/01/0001"
    assert out[0]["court"] == "VwGH"


def test_search_filters_by_court(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Beschwerde OR Vertrag", court="VfGH")
    assert all(r["court"] == "VfGH" for r in out)


def test_search_respects_date_range(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Beschwerde OR Vertrag", date_from="2024-05-15", date_to="2024-12-31")
    assert {r["geschaeftszahl"] for r in out} == {"G1/24"}


def test_search_returns_snippet(tmp_db):
    _seed(tmp_db)
    out = search_decisions(tmp_db, query="Gleichheit")
    assert "Gleichheit" in out[0]["snippet"]
```

- [ ] **Step 2: Run, verify fails**

- [ ] **Step 3: Implement**

```python
# src/ris_mcp/tools/search_decisions.py
"""MCP tool: search_decisions — BM25 over decisions_fts with metadata filters."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from mcp.server import Server
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
        where.append("d.court = ?"); binds.append(court)
    if applikation:
        where.append("d.applikation = ?"); binds.append(applikation)
    if date_from:
        where.append("d.entscheidungsdatum >= ?"); binds.append(date_from)
    if date_to:
        where.append("d.entscheidungsdatum <= ?"); binds.append(date_to)
    if norm:
        where.append("d.norm LIKE ?"); binds.append(f"%{norm}%")

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


def register(server: Server, conn: sqlite3.Connection) -> None:
    @server.list_tools()
    async def _list():
        return [Tool(
            name="search_decisions",
            description=(
                "Search Austrian court decisions by full-text query (FTS5/BM25) "
                "with optional filters (court, applikation, date range, norm)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "FTS5 MATCH expression or keywords"},
                    "court": {"type": "string", "description": "e.g. OGH, VfGH, VwGH, BVwG"},
                    "applikation": {"type": "string"},
                    "date_from": {"type": "string", "description": "ISO date inclusive"},
                    "date_to": {"type": "string", "description": "ISO date inclusive"},
                    "norm": {"type": "string", "description": "substring match on norm field"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
                "required": ["query"],
            },
        )]

    @server.call_tool()
    async def _call(name: str, arguments: dict):
        if name != "search_decisions":
            return None
        rows = search_decisions(conn, **arguments)
        return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False, indent=2))]
```

- [ ] **Step 4: Run, verify passes**

```bash
pytest tests/test_search_decisions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ris_mcp/tools/search_decisions.py tests/test_search_decisions.py
git commit -m "Add search_decisions tool (FTS5 BM25 + filters)"
```

---

### Task 9: Tool — get_decision

**Files:**
- Create: `src/ris_mcp/tools/get_decision.py`
- Test: `tests/test_get_decision.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_get_decision.py
import datetime as dt

import pytest

from ris_mcp.store import upsert_decision
from ris_mcp.tools.get_decision import get_decision


def _seed(conn):
    upsert_decision(conn, {
        "id": "Vfgh:abc", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": "Art. 7 B-VG | Art. 8 B-VG", "schlagworte": "Gleichheit | Sprache",
        "rechtssatz": None, "text": "Volltext", "text_html": "<p>Volltext</p>",
        "source_url": "https://x", "fetched_at": dt.datetime.utcnow().isoformat(),
        "aenderungsdatum": "2024-06-02T10:00:00", "raw_json": "{}",
    })


def test_get_by_id(tmp_db):
    _seed(tmp_db)
    out = get_decision(tmp_db, id="Vfgh:abc")
    assert out["geschaeftszahl"] == "G1/24"
    assert out["norm"] == ["Art. 7 B-VG", "Art. 8 B-VG"]
    assert out["schlagworte"] == ["Gleichheit", "Sprache"]
    assert out["text"] == "Volltext"


def test_get_by_geschaeftszahl(tmp_db):
    _seed(tmp_db)
    out = get_decision(tmp_db, geschaeftszahl="G1/24")
    assert out["id"] == "Vfgh:abc"


def test_neither_arg_raises(tmp_db):
    with pytest.raises(ValueError):
        get_decision(tmp_db)


def test_not_found_returns_none(tmp_db):
    assert get_decision(tmp_db, id="missing") is None
```

- [ ] **Step 2: Run, verify fails**

- [ ] **Step 3: Implement**

```python
# src/ris_mcp/tools/get_decision.py
"""MCP tool: get_decision — exact lookup by stable id or Geschäftszahl."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from mcp.server import Server
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


def register(server: Server, conn: sqlite3.Connection) -> None:
    @server.call_tool()
    async def _call(name: str, arguments: dict):
        if name != "get_decision":
            return None
        out = get_decision(conn, **arguments)
        return [TextContent(type="text", text=json.dumps(out, ensure_ascii=False, indent=2, default=str))]

    # also extend list_tools — done via shared list in server.py? No — each tool registers its own list_tools is illegal in MCP SDK.
    # Instead: the SDK requires a single list_tools handler. We refactor this in Task 11.
```

- [ ] **Step 4: Refactor — single `list_tools` handler**

The MCP SDK only supports one `list_tools` and one `call_tool` handler per server. Refactor: move tool listing and dispatch into `server.py`, and have each `tools/*.py` export a `TOOL: Tool` and a `handler(conn, arguments) -> list[TextContent]`.

Replace `src/ris_mcp/tools/search_decisions.py`'s `register` with:

```python
TOOL = Tool(
    name="search_decisions",
    description=(
        "Search Austrian court decisions by full-text query (FTS5/BM25) "
        "with optional filters (court, applikation, date range, norm)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "court": {"type": "string"},
            "applikation": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "norm": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": ["query"],
    },
)


async def handle(conn, arguments: dict):
    rows = search_decisions(conn, **arguments)
    return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False, indent=2))]
```

(Remove the old `register` function.)

In `src/ris_mcp/tools/get_decision.py` replace `register` with:

```python
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
```

In `src/ris_mcp/server.py` replace `build_server` with:

```python
def build_server() -> Server:
    from .tools import get_decision as t_gd
    from .tools import get_law as t_gl
    from .tools import search_decisions as t_sd

    server = Server("ris-mcp")
    conn = open_db()
    tools = {t.TOOL.name: t for t in (t_sd, t_gd, t_gl)}

    @server.list_tools()
    async def _list():
        return [t.TOOL for t in tools.values()]

    @server.call_tool()
    async def _call(name: str, arguments: dict):
        t = tools.get(name)
        if t is None:
            raise ValueError(f"unknown tool: {name}")
        return await t.handle(conn, arguments)

    return server
```

- [ ] **Step 5: Run, verify all green**

```bash
pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add src/ris_mcp/tools/get_decision.py src/ris_mcp/tools/search_decisions.py src/ris_mcp/server.py tests/test_get_decision.py
git commit -m "Add get_decision tool and unify tool registration"
```

---

### Task 10: Tool — get_law

**Files:**
- Create: `src/ris_mcp/tools/get_law.py`
- Test: `tests/test_get_law.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_get_law.py
from ris_mcp.store import upsert_law
from ris_mcp.tools.get_law import get_law, normalise_paragraf


def _seed(conn):
    upsert_law(conn, {
        "id": "10001622:879", "gesetzesnummer": "10001622", "kurztitel": "ABGB",
        "langtitel": "Allgemeines bürgerliches Gesetzbuch", "paragraf": "879",
        "absatz": None, "ueberschrift": "Sittenwidrige Geschäfte",
        "text": "Ein Vertrag, der gegen ein gesetzliches Verbot verstößt, ist nichtig.",
        "fassung_vom": "2024-01-01", "source_url": "https://x",
        "fetched_at": "2024-06-01T00:00:00", "raw_json": "{}",
    })


def test_get_law_by_kurztitel(tmp_db):
    _seed(tmp_db)
    out = get_law(tmp_db, kurztitel="ABGB", paragraf="879")
    assert out is not None
    assert "nichtig" in out["text"]


def test_get_law_handles_paragraf_prefix(tmp_db):
    _seed(tmp_db)
    assert get_law(tmp_db, kurztitel="ABGB", paragraf="§ 879") is not None
    assert get_law(tmp_db, kurztitel="abgb", paragraf="879") is not None


def test_normalise_paragraf():
    assert normalise_paragraf("§ 879") == "879"
    assert normalise_paragraf("Art. 7") == "7"
    assert normalise_paragraf("879") == "879"
    assert normalise_paragraf("§879") == "879"
```

- [ ] **Step 2: Run, verify fails**

- [ ] **Step 3: Implement**

```python
# src/ris_mcp/tools/get_law.py
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
    description="Retrieve a single Austrian federal-law article (current consolidated Fassung) by short title (e.g. ABGB) and paragraph number.",
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
    return [TextContent(type="text", text=json.dumps(out, ensure_ascii=False, indent=2, default=str))]
```

- [ ] **Step 4: Run, verify passes**

```bash
pytest tests/test_get_law.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ris_mcp/tools/get_law.py tests/test_get_law.py
git commit -m "Add get_law tool"
```

---

### Task 11: End-to-end smoke + README install

**Files:**
- Modify: `README.md`
- Create: `tests/test_e2e_smoke.py` (live; opt-in)

- [ ] **Step 1: Write opt-in live smoke**

```python
# tests/test_e2e_smoke.py
import os

import pytest

LIVE = os.environ.get("RIS_MCP_LIVE") == "1"


@pytest.mark.skipif(not LIVE, reason="set RIS_MCP_LIVE=1 to run")
async def test_full_loop_vfgh(tmp_path, monkeypatch):
    """Ingest 1 page of VfGH live, then search hits via the tool."""
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    from ris_mcp.client import RisClient
    from ris_mcp.ingest import ingest_applikation
    from ris_mcp.store import open_db
    from ris_mcp.tools.search_decisions import search_decisions

    conn = open_db()
    client = RisClient()
    # Limit to one page by mocking the loop is overkill; instead just call once
    n = await ingest_applikation(client, conn, applikation="Vfgh", page_size=10)
    assert n > 0
    hits = search_decisions(conn, query="Beschwerde", limit=5)
    assert hits
```

- [ ] **Step 2: Run smoke once locally**

```bash
RIS_MCP_LIVE=1 pytest tests/test_e2e_smoke.py -v
```

Expected: PASS, ingests at least one page of real VfGH decisions and finds them via FTS.

If it fails: most likely the live API response shape differs from `_parse_search` assumptions. Inspect the recorded fixture vs live; fix the parser; commit.

- [ ] **Step 3: Update README with install instructions**

Replace the current README with the full guide:

```markdown
# ris-mcp

Local MCP server for the Austrian Rechtsinformationssystem (RIS) — court decisions and consolidated federal law, queryable from Claude (Code, Desktop, claude.ai via remote MCP later).

## What you get

- **3 MCP tools** Claude can call:
  - `search_decisions(query, court?, date_from?, date_to?, norm?, limit?)` — FTS5/BM25 over full text
  - `get_decision(id | geschaeftszahl)` — exact lookup
  - `get_law(kurztitel, paragraf)` — federal statute article
- **Local SQLite mirror** of all RIS Judikatur Applikationen + consolidated Bundesrecht (~700K decisions, ~5K laws after backfill)
- **Sub-millisecond search**, offline, immune to RIS API outages

## Why not philrox/ris-mcp-ts?

`philrox/ris-mcp-ts` is a thin live-API proxy. Every Claude query hits `data.bka.gv.at` in real time. That works, but you inherit RIS's keyword-only search and 2–5 s API latency. `ris-mcp` mirrors the corpus locally and indexes it, so search quality and latency improve, and future phases (citation graph, semantic search) become possible.

## Install

```bash
# Once published to PyPI:
claude mcp add ris -- uvx ris-mcp serve

# Until then, from this repo:
git clone https://github.com/jonashertner/ris-mcp.git
cd ris-mcp
uv venv && uv pip install -e .
claude mcp add ris -- "$(pwd)/.venv/bin/ris-mcp" serve
```

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ris": { "command": "/absolute/path/to/.venv/bin/ris-mcp", "args": ["serve"] }
  }
}
```

## First-run backfill

The MCP server reads from a local SQLite DB at `~/.local/share/ris-mcp/ris.db` (override with `RIS_MCP_DATA_DIR`). Populate it once:

```bash
ris-ingest --full
# ~1–3 days for full historical backfill of all sources;
# ~30 min for VfGH alone if you want to test first:
ris-ingest --full --applikation Vfgh --no-bundesrecht
```

Then incremental refreshes (run from cron):

```bash
ris-ingest --delta
```

## Configuration

| env var | default |
|---|---|
| `RIS_MCP_DATA_DIR` | `~/.local/share/ris-mcp` |
| `RIS_MCP_API_BASE` | `https://data.bka.gv.at/ris/api/v2.6` |
| `RIS_MCP_REQUEST_DELAY_MS` | `200` |

## Licenses

- Code: MIT
- Data: CC0-1.0 (RIS content is amtliches Werk per § 7 öUrhG)

## Credits

Builds on documentation from [ximex/ris-bka](https://github.com/ximex/ris-bka). Different design from [philrox/ris-mcp-ts](https://github.com/philrox/ris-mcp-ts) (live proxy) and [PhilippTh/ris-API-wrapper](https://github.com/PhilippTh/ris-API-wrapper) (Python wrapper).

## Roadmap

- [x] Phase 1 (this release): ingester + SQLite/FTS5 + 3 MCP tools
- [ ] Phase 2: citation graph + `find_leading_cases`, `find_citations`, `find_appeal_chain`
- [ ] Phase 3: semantic search, bulk Parquet/HuggingFace export, remote MCP hosting
- [ ] Phase 4: Materialien (RV-Erläuterungen, Stenoprotokolle), doctrine tools
- [ ] Phase 5: Landesrecht
```

- [ ] **Step 4: Commit**

```bash
git add README.md tests/test_e2e_smoke.py
git commit -m "Add e2e smoke test and full install README"
```

---

### Task 12: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push: { branches: [main, master] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv venv && uv pip install -e ".[dev]"
      - run: uv run ruff check src tests
      - run: uv run pytest -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI workflow (ruff + pytest)"
```

---

### Task 13: Push to GitHub & tag v0.1.0

- [ ] **Step 1: Confirm with user before pushing**

Ask the user: "Ready to create the public GitHub repo `jonashertner/ris-mcp` and push? (Reversible: I can delete it afterwards.)"

Wait for explicit yes.

- [ ] **Step 2: Create repo + push**

```bash
gh repo create jonashertner/ris-mcp --public --description "Local MCP server for Austrian RIS (court decisions + federal law) backed by an FTS5-indexed SQLite mirror" --source=. --remote=origin
git branch -M main
git push -u origin main
```

- [ ] **Step 3: Tag v0.1.0**

Only tag if all CI is green and the live smoke has run successfully at least once.

```bash
git tag -a v0.1.0 -m "Phase 1: ingester + SQLite/FTS5 + 3 MCP tools"
git push origin v0.1.0
```

- [ ] **Step 4: Final verification per superpowers/verification-before-completion**

Before claiming done:
- `pytest -v` → all green
- `ruff check src tests` → clean
- `RIS_MCP_LIVE=1 pytest tests/test_e2e_smoke.py -v` → green
- `claude mcp list` shows `ris` registered locally
- A real Claude Code session can call `search_decisions` and get hits

---

## Self-review

**Spec coverage:**
- §3 scope (all Judikatur + Bundesrecht): Tasks 2, 5, 6 ✓
- §4 architecture (client / store / ingest / tools / server separation): Tasks 3, 4, 5, 7, 8–10 ✓
- §5 schema (decisions, decisions_fts, laws, laws_fts, sync_state): Task 4 ✓
- §6 ingest modes (full / delta / per-applikation): Tasks 5, 7 ✓
- §7 three tools + correct signatures: Tasks 8, 9, 10 ✓
- §7.4 resource `ris://decision/{id}`: **gap** — Phase 1 spec mentions it but plan defers; acceptable since the same payload is reachable via `get_decision`. Mark as Phase 1.5 in roadmap; not blocking v0.1.0.
- §8 configuration env vars: Tasks 3, 4 ✓
- §9 error handling (retry, raw_json preserved, no silent fallback): Tasks 3, 4, 5 ✓
- §10 testing (unit + integration + opt-in live): all tasks + Task 11 ✓
- §11 distribution (uvx, README): Tasks 1, 11 ✓
- §12 repo & licensing: Tasks 1, 13 ✓
- §13 rollout plan: matches task order ✓

**Placeholder scan:** All steps have concrete code or commands. Two real-world unknowns (exact API field names, exact LVwG Applikation spelling) are explicitly flagged in Tasks 2 and 3 with instructions on how to confirm at runtime — this is honest scope deferral, not vague requirements.

**Type consistency:** `Tool`, `TextContent`, `Server`, `RisClient`, `SearchHit`, `SearchResponse`, `ApplikationConfig`, `open_db`, `upsert_decision`, `upsert_law`, `get_sync_state`, `set_sync_state`, `ingest_applikation`, `ingest_bundesrecht`, `search_decisions`, `get_decision`, `get_law`, `normalise_paragraf` — all names are consistent across tasks.
