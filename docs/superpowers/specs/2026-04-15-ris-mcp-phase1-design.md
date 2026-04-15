# ris-mcp — Phase 1 Design

**Date:** 2026-04-15
**Status:** Draft → awaiting user review
**Author:** brainstormed with Claude

---

## 1. Goal

Give Claude (Claude Code, Claude Desktop, claude.ai via remote MCP, any MCP-compatible client) high-quality, low-latency access to **Austrian published court decisions and consolidated federal law**, with answer quality meaningfully better than calling the Austrian RIS Web Service API live (the approach taken by `philrox/ris-mcp-ts`).

Phase 1 ships the foundation — ingester, normalised local store, FTS5 search, and a local MCP server with three core tools — that all later phases (citation graph, vector search, remote hosting, bulk dataset export) build on.

## 2. Non-goals (Phase 1)

Explicitly out of scope, each its own future spec:

- Citation graph (decision→decision, decision→statute resolution)
- Vector search / LLM reranking
- Remote MCP hosting (SSE / Streamable HTTP)
- Public web dashboard
- Word add-in / practitioner UI
- Materialien (Erläuterungen, parlamentarische Debatten)
- Landesrecht (state law) and Landesverwaltungsgerichte beyond the published-API scope
- Stripe / billing
- Bulk Parquet / HuggingFace dataset publishing

## 3. Scope of data sources (Phase 1)

All Judikatur "Applikationen" exposed by RIS Web Service v2.6 plus consolidated Bundesrecht:

**Judikatur:**
- `Justiz` (OGH + OLG + LG + BG)
- `Vfgh` (Verfassungsgerichtshof)
- `Vwgh` (Verwaltungsgerichtshof)
- `Bvwg` (Bundesverwaltungsgericht)
- `Lvwg` (9 Landesverwaltungsgerichte, one Applikation per Land)
- `Dsk` / `Dsb` (Datenschutzbehörde)
- `Gbk` (Gleichbehandlungskommission)
- Any additional Judikatur Applikationen the API enumerates at build time

**Statutes:**
- `Bundesrecht` (consolidated federal law, current Fassung)

The exact Applikation enum is pinned during implementation by querying `https://data.bka.gv.at/ris/api/v2.6/Judikatur` Help and storing the full list in `applikation_registry.py`.

## 4. Architecture

```
┌────────────────────────────────────────┐
│  Claude (Code / Desktop / claude.ai)    │
└────────────────┬───────────────────────┘
                 │ MCP stdio
┌────────────────▼───────────────────────┐
│  ris_mcp.server                         │
│  Tools:                                 │
│   - search_decisions                    │
│   - get_decision                        │
│   - get_law                             │
└────────────────┬───────────────────────┘
                 │ SQL (read-only)
┌────────────────▼───────────────────────┐
│  SQLite — ~/.local/share/ris-mcp/ris.db │
│  Tables:                                │
│   - decisions (canonical)               │
│   - decisions_fts (FTS5)                │
│   - laws (canonical)                    │
│   - laws_fts (FTS5)                     │
│   - sync_state                          │
│   - applikation                         │
└────────────────▲───────────────────────┘
                 │ writes
┌────────────────┴───────────────────────┐
│  ris_mcp.ingest                         │
│  - RisClient (HTTP + retry)             │
│  - RisIngester (generic, paginated)     │
│  - ApplikationConfig registry           │
│  - delta sync via Aenderungsdatum       │
│  - CLI: ris-ingest [--full | --delta]   │
└────────────────┬───────────────────────┘
                 │ HTTPS GET
┌────────────────▼───────────────────────┐
│  data.bka.gv.at/ris/api/v2.6            │
└────────────────────────────────────────┘
```

### 4.1 Module layout

```
ris-mcp/
├── pyproject.toml
├── README.md
├── LICENSE                      # MIT
├── DATA_LICENSE                 # CC0-1.0 (RIS data is amtliches Werk, § 7 UrhG)
├── docs/
│   └── superpowers/specs/
│       └── 2026-04-15-ris-mcp-phase1-design.md
├── src/ris_mcp/
│   ├── __init__.py
│   ├── client.py                # RisClient: HTTP, retry, rate-limit-aware
│   ├── applikation.py           # ApplikationConfig + registry
│   ├── ingest.py                # RisIngester (generic, paginated)
│   ├── ingest_bundesrecht.py    # Bundesrecht-specific ingester
│   ├── store.py                 # SQLite open + schema migrate + FTS5 helpers
│   ├── schema.sql               # Canonical schema
│   ├── server.py                # MCP server (stdio); registers tools
│   ├── tools/
│   │   ├── search_decisions.py
│   │   ├── get_decision.py
│   │   └── get_law.py
│   └── cli.py                   # `ris-ingest`, `ris-mcp` entrypoints
├── tests/
│   ├── test_client.py           # mocked HTTP
│   ├── test_ingest.py           # mocked client → in-memory SQLite
│   ├── test_store.py
│   └── test_tools.py            # MCP tool contract tests
└── .github/workflows/
    ├── ci.yml                   # ruff + pytest
    └── daily-sync.yml           # optional self-hosted runner; off by default
```

### 4.2 Key boundaries

- **`client.py`** — the only module that talks HTTP. Knows nothing about SQLite. Exposes `RisClient.search(applikation, **filters, page) -> SearchResponse` and `RisClient.fetch_document(doc_url) -> bytes`.
- **`ingest.py`** — orchestrates a sync run. Reads from `RisClient`, writes to `store`. Knows the API shape and the canonical schema, nothing else.
- **`store.py`** — owns SQLite. Pure SQL, no HTTP. Read API used by `tools/`, write API used by `ingest`.
- **`tools/`** — each MCP tool is one file with a thin function: parse args → `store` query → format result.
- **`server.py`** — wires MCP SDK to tools. No business logic.

This separation is the same shape as `caselaw-repo-1` and is what makes the per-court explosion unnecessary — Austrian RIS is one API, so we have one ingester, parameterised by `ApplikationConfig`.

## 5. Data model

### 5.1 `decisions` (canonical)

```sql
CREATE TABLE decisions (
  id              TEXT PRIMARY KEY,        -- stable: "<applikation>:<dokument_id>"
  applikation     TEXT NOT NULL,           -- 'Justiz', 'Vfgh', ...
  court           TEXT NOT NULL,           -- normalised: 'OGH', 'VfGH', 'BVwG', ...
  geschaeftszahl  TEXT NOT NULL,           -- e.g. '6Ob123/24a'
  entscheidungsdatum DATE,
  rechtssatznummer TEXT,                   -- nullable; some entries are RS, some Entscheidungstexte
  dokumenttyp     TEXT,                    -- 'Entscheidungstext' | 'Rechtssatz'
  norm            TEXT,                    -- pipe-joined statute refs as published
  schlagworte     TEXT,                    -- pipe-joined keywords
  rechtssatz      TEXT,                    -- short Leitsatz text if present
  text            TEXT,                    -- full Entscheidungstext (HTML stripped)
  text_html       TEXT,                    -- raw HTML for fidelity
  source_url      TEXT,                    -- canonical RIS URL
  fetched_at      TIMESTAMP NOT NULL,
  aenderungsdatum TIMESTAMP,               -- API's last-modified; drives delta sync
  raw_json        TEXT                     -- full API response for forensic recovery
);
CREATE INDEX idx_decisions_court_date ON decisions(court, entscheidungsdatum DESC);
CREATE INDEX idx_decisions_geschaeftszahl ON decisions(geschaeftszahl);
CREATE INDEX idx_decisions_aenderung ON decisions(aenderungsdatum);
```

### 5.2 `decisions_fts`

```sql
CREATE VIRTUAL TABLE decisions_fts USING fts5(
  geschaeftszahl, court, norm, schlagworte, rechtssatz, text,
  content='decisions', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
```
Triggers keep FTS in sync on INSERT/UPDATE/DELETE.

### 5.3 `laws` (Bundesrecht consolidated)

```sql
CREATE TABLE laws (
  id              TEXT PRIMARY KEY,        -- "<gesetzesnummer>:<paragraf>"
  gesetzesnummer  TEXT NOT NULL,           -- e.g. '10001622' (ABGB)
  kurztitel       TEXT,                    -- e.g. 'ABGB'
  langtitel       TEXT,
  paragraf        TEXT NOT NULL,           -- '§ 879' or 'Art. 7'
  absatz          TEXT,                    -- nullable
  ueberschrift    TEXT,
  text            TEXT NOT NULL,
  fassung_vom     DATE,
  source_url      TEXT,
  fetched_at      TIMESTAMP NOT NULL,
  raw_json        TEXT
);
CREATE INDEX idx_laws_kurztitel ON laws(kurztitel);
```

### 5.4 `sync_state`

```sql
CREATE TABLE sync_state (
  applikation     TEXT PRIMARY KEY,
  last_full_sync  TIMESTAMP,
  last_delta_sync TIMESTAMP,
  watermark_aenderungsdatum TIMESTAMP,
  total_docs      INTEGER
);
```

## 6. Ingestion

### 6.1 Modes

```
ris-ingest --full                    # historical backfill, all Applikationen
ris-ingest --full --applikation Vfgh # one source
ris-ingest --delta                   # incremental, since last watermark
```

### 6.2 Algorithm (per Applikation)

1. Read `watermark_aenderungsdatum` (NULL for `--full`).
2. Page through `GET /ris/api/v2.6/Judikatur?Applikation=<X>&Aenderungsdatum=>=<watermark>&DokumenteProSeite=100&Seitennummer=N` until empty.
3. For each hit:
   - Extract metadata from search response.
   - If `text` URL present, fetch full document (HTML), strip to plain text, store both.
   - Upsert into `decisions` keyed by `id`. FTS5 trigger handles index.
4. After pagination completes, advance watermark to `max(aenderungsdatum)` seen.
5. Commit per page (batch size 100). Crash-safe.

### 6.3 Politeness

- Hard-coded `User-Agent: ris-mcp/<version> (+github.com/jonashertner/ris-mcp)`.
- Per-request sleep configurable (default 200 ms between requests).
- Exponential backoff on 429 / 5xx (max 5 retries).
- Concurrency = 1 by default; bumped to 4 only if RIS shows no rate-limit signals after 24 h of operation.

### 6.4 Bundesrecht

Separate `ingest_bundesrecht.py` because the response shape differs. Same API base, `Applikation=Br`. Per-Gesetz pagination, then per-Paragraf extraction. Ships in Phase 1 because (a) ~5K laws is small, (b) Claude queries naturally combine "what does § X say" with "what cases interpret it."

## 7. MCP server (Phase 1 tools)

Transport: **stdio only**. The server is a Python process invoked by Claude Code / Desktop config. Uses the official `mcp` Python SDK.

### 7.1 `search_decisions`

```
search_decisions(
  query: str,                       # FTS5 MATCH expression or natural keywords
  court: str | None = None,         # 'OGH', 'VfGH', 'VwGH', 'BVwG', 'LVwG', ...
  applikation: str | None = None,   # raw RIS Applikation code if user prefers
  date_from: str | None = None,     # ISO date
  date_to:   str | None = None,
  norm:      str | None = None,     # substring match on norm field
  limit:     int = 20               # 1..100
) -> list[{id, court, geschaeftszahl, entscheidungsdatum, snippet, source_url}]
```

Implementation: SQLite `decisions_fts MATCH ?` + filter joins, BM25 ranking via `bm25(decisions_fts)`, snippet via `snippet(decisions_fts, ...)`. No LLM rerank in Phase 1.

### 7.2 `get_decision`

```
get_decision(
  id: str | None = None,            # canonical id from search
  geschaeftszahl: str | None = None # alternate lookup
) -> {
  id, court, geschaeftszahl, entscheidungsdatum,
  dokumenttyp, norm: list[str], schlagworte: list[str],
  rechtssatz: str | None, text: str, source_url
}
```

If both args missing → error. If geschaeftszahl matches multiple → return list of disambiguation stubs.

### 7.3 `get_law`

```
get_law(
  kurztitel: str,                   # 'ABGB', 'StGB', 'B-VG', ...
  paragraf:  str                    # '879', 'Art. 7', '§ 879'
) -> {
  kurztitel, langtitel, paragraf, absatz, ueberschrift,
  text, fassung_vom, source_url
}
```

Normalises `paragraf` input ('§ 879' / '879' / 'Art. 7' all map). Returns 404-shaped error if not found.

### 7.4 Resource endpoints

Phase 1 exposes one MCP resource: `ris://decision/{id}` → returns the same payload as `get_decision`. Lets Claude include decisions as conversation context.

## 8. Configuration

| Setting | Env var | Default |
|---|---|---|
| Data directory | `RIS_MCP_DATA_DIR` | `~/.local/share/ris-mcp` |
| API base URL | `RIS_MCP_API_BASE` | `https://data.bka.gv.at/ris/api/v2.6` |
| Request delay (ms) | `RIS_MCP_REQUEST_DELAY_MS` | `200` |
| Concurrency | `RIS_MCP_CONCURRENCY` | `1` |
| User-Agent suffix | `RIS_MCP_UA_SUFFIX` | `""` |

No config file in Phase 1 — env vars are enough.

## 9. Error handling

- **API down / 5xx** — ingester retries with backoff; after 5 fails logs and skips; MCP tools return a structured error with `source: "ris_api_unavailable"`.
- **Schema drift** — `raw_json` is preserved on every row, so a future migration can re-extract fields without re-fetching.
- **Tool input validation** — Pydantic models on tool args; invalid inputs return a structured error, never crash the server.
- **No silent fallbacks** — if FTS index is missing, the tool errors with `"run ris-ingest --full first"`, not empty results.

## 10. Testing

- **Unit tests** for `client.py` against recorded HTTP fixtures (no live calls in CI).
- **Integration tests** that wire `ingest → in-memory SQLite → tool query` with mocked client.
- **One live smoke test** behind `RIS_MCP_LIVE=1` env flag, off by default in CI: hits one VfGH page, asserts schema. Run before each release.
- **MCP contract tests** — invoke each tool via the MCP SDK's in-process test client, assert response shape.
- TDD workflow per superpowers TDD skill: red → green → refactor for each tool.

## 11. Distribution & install

- Published to PyPI as `ris-mcp` (Phase 1 may keep it `pip install git+https://...` until tooling matures).
- One-line install for Claude Code:
  ```
  claude mcp add ris -- uvx ris-mcp serve
  ```
- Claude Desktop config snippet in README.
- First run prints "no data yet, run `ris-ingest --full` (≈1–3 days)" rather than failing silently.

## 12. Repo & licensing

- **GitHub:** `jonashertner/ris-mcp`, public from day 1
- **Code license:** MIT
- **Data license:** CC0-1.0 (Austrian RIS content is amtliches Werk per § 7 UrhG)
- **README** explicitly references and credits `philrox/ris-mcp-ts`, `PhilippTh/ris-API-wrapper`, `ximex/ris-bka` — and explains the design difference (local mirror vs live proxy)

## 13. Rollout plan (Phase 1 only)

1. Scaffold repo, push empty initial commit
2. TDD `client.py` + `applikation` registry (≈0.5 day)
3. TDD `store.py` + schema (≈0.5 day)
4. TDD `ingest.py` + Bundesrecht ingester (≈1 day)
5. TDD MCP server + 3 tools (≈1 day)
6. Smoke-test full backfill of `Vfgh` only (smallest corpus, ~30K decisions) end-to-end
7. Document install, push v0.1.0 tag
8. Kick off historical backfill of remaining Applikationen in background

Total estimate: ~3–5 working days for a usable v0.1.0; full backfill runs in background after that.

## 14. Future phases (sketch only — separate specs)

- **Phase 2:** Citation extraction & resolution → citation graph; `find_leading_cases`, `find_citations`, `find_appeal_chain` tools
- **Phase 3:** Vector search + semantic rerank; bulk Parquet export + HuggingFace dataset publish; remote MCP at `mcp.ris-mcp.at` (or similar); domain
- **Phase 4:** Materialien (Erläuterungen, RV-Begründungen, Nationalrats-Stenoprotokolle); doctrine tools
- **Phase 5:** Landesrecht + LVwG full coverage; cross-language (none — DE only); commentary integration if a free Austrian Online-Kommentar emerges

---

## Self-review checklist

- [x] No "TBD" or placeholder sections (exact API field names noted as "pinned during implementation," which is honest scope deferral, not vagueness)
- [x] Architecture matches feature list — every tool maps to a table that the ingester populates
- [x] Scope is one phase, single implementation plan worth of work (~3–5 days)
- [x] Each requirement is unambiguous (tool signatures concrete, schema concrete, transport concrete)
