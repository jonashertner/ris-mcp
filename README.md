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
