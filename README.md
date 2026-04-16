# ris-mcp

> **👉 For end users: see [jonashertner.github.io/ris-mcp](https://jonashertner.github.io/ris-mcp/) for the three-command install.**

Local MCP server for the Austrian Rechtsinformationssystem (RIS) — court decisions and consolidated federal law, queryable from Claude (Code, Desktop, claude.ai).

[![CI](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml)

## What

`ris-mcp` maintains a locally-mirrored, FTS5-indexed SQLite copy of the full Austrian RIS corpus and exposes it to Claude via MCP. Unlike a live-API proxy, the local mirror delivers better search quality (BM25 over full text), sub-millisecond latency, offline capability, and a foundation for citation-graph and semantic-search features.

## Install (users)

See the [landing page](https://jonashertner.github.io/ris-mcp/).

## Develop (contributors)

```bash
git clone https://github.com/jonashertner/ris-mcp.git
cd ris-mcp
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -v
```

Run the MCP server locally:

```bash
.venv/bin/ris-mcp serve
```

Kick off a full backfill (2–3 days):

```bash
.venv/bin/ris-ingest --full
```

Emit coverage stats:

```bash
.venv/bin/ris-ingest coverage --out docs/stats.json
```

## Licenses

- Code: MIT
- Data: CC0-1.0 (amtliches Werk per § 7 öUrhG)

## Credits

- [ximex/ris-bka](https://github.com/ximex/ris-bka) — early (2013) RIS OGD documentation
- [opencaselaw.ch](https://opencaselaw.ch) — architectural inspiration (Swiss case law)
