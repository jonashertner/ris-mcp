# ris-mcp

> **👉 See [jonashertner.github.io/ris-mcp](https://jonashertner.github.io/ris-mcp/) for the project page and self-build instructions.**

Proof-of-concept local MCP server for the Austrian Rechtsinformationssystem
(RIS) — court decisions and consolidated federal law, queryable from MCP clients.

[![CI](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml)

## What

`ris-mcp` demonstrates how to ingest Austrian RIS data into a local,
FTS5-indexed SQLite database and expose it through MCP. The repository is
published for others to study, fork, and take forward. It is not a supported
service or product, and it has no delivery roadmap.

## Install (users)

See the [landing page](https://jonashertner.github.io/ris-mcp/).

No public pre-built corpus or hosted endpoint is provided. To exercise the
proof of concept, build a local database from the official RIS API with
`ris-ingest --full`.

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

Kick off a full backfill (currently about 3–4 days):

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
