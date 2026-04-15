# ris-mcp Phase 1.5 — Lay-user distribution layer

**Date:** 2026-04-15
**Status:** Draft → awaiting user review
**Predecessor:** `2026-04-15-ris-mcp-phase1-design.md` (Phase 1 shipped at tag `v0.1.0`)

---

## 1. Goal

Make `ris-mcp` installable by a non-developer in three copy-paste commands, backed by a pre-built full-corpus SQLite dataset hosted on HuggingFace so they skip the 2–3 day ingest.

## 2. Non-goals (stays out of this phase)

- Remote hosted MCP endpoint (`mcp.ris-mcp.at` SSE/HTTP) — Phase 3
- Web search UI on the landing page
- Custom domain for GitHub Pages
- Automated backfill in CI (GH Actions 6 h cap makes it impossible)
- Word add-in / practitioner UI
- Citation graph, semantic search, Materialien — Phases 2–4

## 3. User decisions locked in

| # | Choice | Rationale |
|---|---|---|
| Q1 | **B — Full corpus on HF** | User will run backfill in background on their machine; Pages + PyPI ship now, dataset swaps in when ready |
| Q2 | **A — Trusted Publisher via GH Actions** | No API tokens in repo; modern best practice; one-time manual PyPI project registration |
| Q3 | **A — Single static HTML + Tailwind CDN** | No build step; Pages serves straight from `/docs/` |

## 4. Sub-components

### 4.1 PyPI release pipeline

- **Version bump:** `0.1.0.dev0` → `0.2.0` in `pyproject.toml` and `src/ris_mcp/__init__.py`. The already-pushed `v0.1.0` tag stays as the "first working code" milestone; Phase 1.5 ships as `v0.2.0` ("first releasable wheel + pre-built dataset + public landing page").
- **Manual one-time setup (user):** register `ris-mcp` on PyPI, configure Trusted Publisher for `jonashertner/ris-mcp` workflow `release.yml` on environment `pypi`.
- **`.github/workflows/release.yml`:** triggered on `v*` tags; steps: checkout → setup-uv → `uv build` → `pypa/gh-action-pypi-publish@release/v1` with `id-token: write`.
- **Test before ship:** a dry-run publish to TestPyPI from a `v*-rc1` tag (optional but recommended).

### 4.2 `ris-ingest --import-from-hf` command

New subcommand on the existing `ris-ingest` CLI (via click subgroup or a third entrypoint — pick subgroup; see §6):

```
ris-ingest import-from-hf [--repo voilaj/austrian-caselaw] [--revision main]
```

Behaviour:
1. Resolve target path: `$RIS_MCP_DATA_DIR/ris.db` (same as `open_db`'s default).
2. If target exists: abort unless `--force`.
3. Use `huggingface_hub.hf_hub_download` to fetch `ris.db` from the repo.
4. Verify against `ris.db.sha256` side-file (also downloaded).
5. Move into place atomically.
6. Print summary (size, decisions count read from the DB, last aenderungsdatum).

Dependencies: add `huggingface_hub>=0.24` to `pyproject.toml`. No other new deps.

**Fail-soft contract (Phase 1.5 v1):** if the HF repo doesn't exist yet (dataset not uploaded), the command prints a clear "dataset not yet published, see roadmap: <Pages URL>" and exits 2 — not a crash. This lets us ship the command before the backfill completes.

### 4.3 `ris-coverage` command

New click command that reads `~/.local/share/ris-mcp/ris.db` and emits a JSON stats document used by both the landing page and the HF dataset card:

```json
{
  "generated_at": "2026-04-15T22:00:00Z",
  "total_decisions": 712834,
  "decisions_by_court": {"OGH": 423012, "VfGH": 24110, "VwGH": ...},
  "total_laws": 5412,
  "total_articles": 134589,
  "last_aenderungsdatum": "2026-04-14T18:32:00",
  "corpus_span": {"earliest": "1918-01-01", "latest": "2026-04-14"},
  "schema_version": 1
}
```

Output to `docs/stats.json` by default (overridable with `--out`). Committed to the repo so the Pages site reads it at build time. Run manually after ingest.

### 4.4 GitHub Pages landing page

**Location:** `docs/index.html` + `docs/stats.json` + `docs/assets/` (optional screenshots). **Configure:** Pages → "Deploy from branch" → `main` / `/docs`.

**Why `docs/` and not a separate `gh-pages` branch:** specs and plans already live under `docs/superpowers/` — keeping Pages content alongside them avoids branch bifurcation. Pages ignores subdirs unless referenced.

**Content outline** (single-page, ~300 lines HTML):

1. **Hero** — "Austrian case law + federal statutes, inside Claude." · 2-sentence pitch · Claude-Desktop copy button → config snippet · "View on GitHub" button
2. **What you get** — 3-column feature list: Case law (~700K decisions across all published Austrian courts), Statutes (BrKons consolidated federal law), MCP tools (search_decisions / get_decision / get_law)
3. **Install** — 3 code blocks:
   - (a) Install `uv` (one-liner per OS, link to official docs)
   - (b) `claude mcp add ris -- uvx ris-mcp serve` (shown immediately as the simple form; while PyPI isn't live yet, page shows a "not yet on PyPI — use git form" callout with `uvx --from git+https://github.com/jonashertner/ris-mcp ris-mcp serve`; callout disappears in a one-line HTML edit when PyPI ships)
   - (c) `ris-ingest import-from-hf` to get the pre-built DB (shown with a "dataset coming Q2 2026" banner until the HF upload lands; banner removed when ready)
4. **Claude Desktop config** — copy-pasteable JSON snippet for `claude_desktop_config.json`, plus identical instructions for ChatGPT/Cursor/Windsurf
5. **Why not `philrox/ris-mcp-ts`** — comparison table (live proxy vs indexed mirror)
6. **Corpus stats** — reads `stats.json` inline; big numbers with per-court breakdown
7. **Roadmap** — Phases 2–5 in plain English
8. **Credits** — ximex / philrox / PhilippTh / opencaselaw.ch as inspiration
9. **Footer** — MIT code · CC0 data · legal disclaimer (no legal advice; data is amtliches Werk)

**Stack:** single `index.html` with Tailwind CDN `<script src="https://cdn.tailwindcss.com">` + minimal vanilla JS to fetch `stats.json` and render numbers.

### 4.5 Backfill orchestration (user action, not in repo)

User runs locally in the background:

```bash
nohup .venv/bin/ris-ingest --full > ingest.log 2>&1 &
```

When it finishes (2–3 days), user runs:

```bash
ris-coverage --out docs/stats.json
sqlite3 ~/.local/share/ris-mcp/ris.db "PRAGMA wal_checkpoint(TRUNCATE);"
shasum -a 256 ~/.local/share/ris-mcp/ris.db > ~/.local/share/ris-mcp/ris.db.sha256

# upload to HF (first time: creates the repo)
huggingface-cli login
huggingface-cli upload voilaj/austrian-caselaw \
  ~/.local/share/ris-mcp/ris.db ris.db
huggingface-cli upload voilaj/austrian-caselaw \
  ~/.local/share/ris-mcp/ris.db.sha256 ris.db.sha256
```

Then user updates the Pages site to remove the "coming soon" banner and commits the refreshed `stats.json`. Two-line HTML edit + one commit.

**This is documented in a separate `docs/publishing-the-dataset.md` runbook, not automated in Phase 1.5.** Automation (GH-hosted release workflow triggered by a fresh backfill) is a Phase 3 concern.

### 4.6 README update

Top of `README.md` gets:
- Pages URL banner
- PyPI shields.io badge (once live)
- HuggingFace dataset badge (once live)

Install section gets collapsed into a "For end users: see <Pages URL>. For developers: clone + uv + dev workflow" split. Reduces duplication.

## 5. What ships in v0.2.0 vs later

| | v0.2.0 (this phase) | swap-in later |
|---|---|---|
| Version bump 0.1.0.dev0 → 0.2.0 | ✅ | |
| `ris-ingest import-from-hf` cmd | ✅ (fail-soft if no dataset) | |
| `ris-coverage` cmd | ✅ | |
| `docs/index.html` Pages site | ✅ (with "coming soon" banners) | banners removed when data ships |
| PyPI release workflow | ✅ (runs on `v0.2.0` tag) | |
| PyPI trusted publisher registered | user one-time manual | |
| Full-corpus backfill on user's machine | started | 2–3 days later completes |
| HF dataset `voilaj/austrian-caselaw` uploaded | — | after backfill |
| Pages site `stats.json` refreshed | with placeholder zeros | real numbers post-backfill |

## 6. Open secondary decisions — my picks (override any)

| # | Question | My pick | Why |
|---|---|---|---|
| S1 | HF repo name | `voilaj/austrian-caselaw` | Matches `voilaj/swiss-caselaw` convention. Use existing HF account. |
| S2 | CLI shape for import | Add as subcommand: `ris-ingest import-from-hf` | Reuses existing entrypoint; fewer scripts to remember |
| S3 | Pages URL | `jonashertner.github.io/ris-mcp` (no custom domain) | Free, zero-config, good enough |
| S4 | When to register PyPI project | Before v0.2.0 tag push | Publish workflow will fail without it; a 2-min manual step on pypi.org |
| S5 | Should I start the full backfill tonight? | Yes | Kicks off the 2–3 day clock while we build the rest |

## 7. Rollout sequence

1. Start the full backfill in the background **now** (S5 = yes)
2. Bump version, build Pages site + HF import cmd + coverage cmd (does not depend on backfill)
3. User registers `ris-mcp` on PyPI + configures Trusted Publisher
4. Tag `v0.2.0` → PyPI release fires → site goes live
5. Wait for backfill (2–3 days)
6. User uploads DB to HF + refreshes stats + removes "coming soon" banners
7. Tag `v0.2.1` (docs-only) to advertise the dataset

## 8. Self-review

- No TBDs; secondary decisions all given concrete picks (S1–S5)
- Scope fits one implementation plan (~1–2 days of coding, excl. the backfill itself)
- Matches phase decomposition discipline — citation graph / remote MCP stay in Phases 2–3
- Fail-soft `--import-from-hf` avoids coupling v0.2.0 release to the backfill clock
