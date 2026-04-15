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
