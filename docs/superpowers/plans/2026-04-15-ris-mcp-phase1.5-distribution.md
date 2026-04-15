# ris-mcp Phase 1.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Ship `v0.2.0` — a PyPI-publishable release, a `ris-ingest import-from-hf` command for lay users to pull a pre-built corpus, a `ris-coverage` stats emitter, and a single-page GitHub Pages landing site.

**Architecture:** Add `huggingface_hub` dep + two new CLI subcommands (`import-from-hf`, `coverage`) + static `docs/index.html` served from `main` via Pages. No changes to the core ingester, store, or MCP server. Migrate the single `ris-ingest` command to a click group to host subcommands.

**Tech Stack:** same as Phase 1 + `huggingface_hub>=0.24` + Tailwind CDN (no build step).

**Spec:** `docs/superpowers/specs/2026-04-15-ris-mcp-phase1.5-distribution-design.md`

---

## File structure

```
ris-mcp/
├── docs/
│   ├── index.html                       # NEW (Pages root)
│   ├── stats.json                       # NEW (generated; placeholder until backfill done)
│   └── publishing-the-dataset.md        # NEW (runbook)
├── src/ris_mcp/
│   ├── cli.py                           # MODIFY (flat cmd → group with subcommands)
│   ├── coverage.py                      # NEW (ris-coverage body)
│   └── hf_import.py                     # NEW (import-from-hf body)
├── tests/
│   ├── test_coverage.py                 # NEW
│   ├── test_hf_import.py                # NEW
│   └── test_cli.py                      # MODIFY (new group structure)
├── .github/workflows/
│   ├── ci.yml                           # existing
│   └── release.yml                      # NEW
├── .gitignore                           # MODIFY (ignore ingest.log)
├── README.md                            # MODIFY (banner + simpler install)
└── pyproject.toml                       # MODIFY (version, huggingface_hub dep)
```

---

### Task 1: Version bump + dep + gitignore

**Files:**
- Modify: `pyproject.toml`, `src/ris_mcp/__init__.py`, `.gitignore`

- [ ] **Step 1:** Edit `pyproject.toml`:
  - Change `version = "0.1.0.dev0"` → `version = "0.2.0"`
  - In `dependencies`, append `"huggingface_hub>=0.24"`
- [ ] **Step 2:** Edit `src/ris_mcp/__init__.py`: `__version__ = "0.2.0"`
- [ ] **Step 3:** Edit `.gitignore`: append `ingest.log` (the backfill log)
- [ ] **Step 4:** Reinstall: `uv pip install -e ".[dev]"`
- [ ] **Step 5:** Run full pytest: `.venv/bin/pytest -v` → must remain 40 passed / 1 skipped
- [ ] **Step 6:** Commit:
  ```
  git add pyproject.toml src/ris_mcp/__init__.py .gitignore
  git commit -m "Bump version to 0.2.0 and add huggingface_hub dep"
  ```

---

### Task 2: Migrate CLI to click group; add `coverage` subcommand

**Files:**
- Create: `src/ris_mcp/coverage.py`, `tests/test_coverage.py`
- Modify: `src/ris_mcp/cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Write failing tests** in `tests/test_coverage.py`:

```python
# tests/test_coverage.py
import datetime as dt
import json

from ris_mcp.coverage import generate_coverage
from ris_mcp.store import upsert_decision, upsert_law


def _seed(conn):
    now = dt.datetime.utcnow().isoformat()
    upsert_decision(conn, {
        "id": "Vfgh:1", "applikation": "Vfgh", "court": "VfGH",
        "geschaeftszahl": "G1/24", "entscheidungsdatum": "2024-06-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "x", "text_html": None, "source_url": None,
        "fetched_at": now, "aenderungsdatum": "2024-06-02T10:00:00",
        "raw_json": "{}",
    })
    upsert_decision(conn, {
        "id": "Vwgh:1", "applikation": "Vwgh", "court": "VwGH",
        "geschaeftszahl": "Ra1/24", "entscheidungsdatum": "2024-05-01",
        "rechtssatznummer": None, "dokumenttyp": "Entscheidungstext",
        "norm": None, "schlagworte": None, "rechtssatz": None,
        "text": "y", "text_html": None, "source_url": None,
        "fetched_at": now, "aenderungsdatum": "2024-05-02T10:00:00",
        "raw_json": "{}",
    })
    upsert_law(conn, {
        "id": "10001622:879", "gesetzesnummer": "10001622",
        "kurztitel": "ABGB", "langtitel": "ABGB",
        "paragraf": "879", "absatz": None, "ueberschrift": None,
        "text": "nichtig.", "fassung_vom": "2024-01-01", "source_url": None,
        "fetched_at": now, "raw_json": "{}",
    })


def test_coverage_counts(tmp_db):
    _seed(tmp_db)
    out = generate_coverage(tmp_db)
    assert out["total_decisions"] == 2
    assert out["total_laws"] == 1
    assert out["decisions_by_court"] == {"VfGH": 1, "VwGH": 1}
    assert out["corpus_span"]["earliest"] == "2024-05-01"
    assert out["corpus_span"]["latest"] == "2024-06-01"
    assert out["last_aenderungsdatum"] == "2024-06-02T10:00:00"
    assert out["schema_version"] == 1
    assert "generated_at" in out


def test_coverage_empty_db(tmp_db):
    out = generate_coverage(tmp_db)
    assert out["total_decisions"] == 0
    assert out["total_laws"] == 0
    assert out["decisions_by_court"] == {}
    assert out["corpus_span"]["earliest"] is None
    assert out["corpus_span"]["latest"] is None
    assert out["last_aenderungsdatum"] is None


def test_coverage_output_is_json_serialisable(tmp_db):
    _seed(tmp_db)
    out = generate_coverage(tmp_db)
    json.dumps(out)  # raises if not serialisable
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_coverage.py -v` → ImportError expected.

- [ ] **Step 3: Implement `src/ris_mcp/coverage.py`:**

```python
"""Coverage/stats report for the local corpus. Emits JSON consumed by
docs/stats.json and the Pages site.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any

SCHEMA_VERSION = 1


def generate_coverage(conn: sqlite3.Connection) -> dict[str, Any]:
    total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    total_laws = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]

    by_court_rows = conn.execute(
        "SELECT court, COUNT(*) FROM decisions GROUP BY court ORDER BY court"
    ).fetchall()
    by_court = {row[0]: row[1] for row in by_court_rows}

    span = conn.execute(
        "SELECT MIN(entscheidungsdatum), MAX(entscheidungsdatum) FROM decisions"
    ).fetchone()
    last_aenderung = conn.execute(
        "SELECT MAX(aenderungsdatum) FROM decisions"
    ).fetchone()[0]

    return {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total_decisions": total_decisions,
        "total_laws": total_laws,
        "decisions_by_court": by_court,
        "corpus_span": {"earliest": span[0], "latest": span[1]},
        "last_aenderungsdatum": last_aenderung,
        "schema_version": SCHEMA_VERSION,
    }
```

- [ ] **Step 4:** `.venv/bin/pytest tests/test_coverage.py -v` → 3 PASS.

- [ ] **Step 5: Migrate `cli.py` to click group + add `coverage` subcommand**

Replace the existing `cli.py` body with the group form:

```python
# src/ris_mcp/cli.py
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click

from . import server as mcp_server
from .applikation import REGISTRY
from .client import RisClient
from .coverage import generate_coverage
from .ingest import ingest_applikation
from .ingest_bundesrecht import ingest_bundesrecht
from .store import open_db


@click.group(name="ris-ingest", invoke_without_command=True)
@click.option("--full", is_flag=True, help="Full historical backfill")
@click.option("--delta", is_flag=True, help="Incremental sync since last watermark")
@click.option("--applikation", default=None, help="Restrict to one Applikation code")
@click.option(
    "--include-bundesrecht/--no-bundesrecht", default=True,
    help="Also ingest Bundesrecht (consolidated federal law)",
)
@click.pass_context
def ingest_main(
    ctx: click.Context,
    full: bool, delta: bool,
    applikation: str | None, include_bundesrecht: bool,
) -> None:
    """Ingest or sync Austrian RIS judikatur + Bundesrecht into the local SQLite."""
    if ctx.invoked_subcommand is not None:
        return
    if not (full or delta):
        raise click.UsageError("specify --full, --delta, or a subcommand")

    async def run() -> None:
        conn = open_db()
        async with RisClient() as client:
            codes = [applikation] if applikation else [a.code for a in REGISTRY]
            for code in codes:
                click.echo(f"==> {code}")
                n = await ingest_applikation(
                    client, conn, applikation=code, delta=delta,
                )
                click.echo(f"    {n} decisions")
            if include_bundesrecht:
                click.echo("==> Bundesrecht")
                n = await ingest_bundesrecht(client, conn)
                click.echo(f"    {n} articles")

    asyncio.run(run())


@ingest_main.command("coverage")
@click.option(
    "--out", default="docs/stats.json",
    type=click.Path(dir_okay=False, writable=True),
    help="Output path for the JSON stats file",
)
def coverage_cmd(out: str) -> None:
    """Emit a JSON stats report for the current local corpus."""
    conn = open_db()
    data = generate_coverage(conn)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    click.echo(
        f"wrote {out}: {data['total_decisions']} decisions, {data['total_laws']} laws"
    )


@click.command("ris-mcp")
@click.argument("subcommand", type=click.Choice(["serve"]), default="serve")
def mcp_main(subcommand: str) -> None:
    if subcommand == "serve":
        mcp_server.main()
```

- [ ] **Step 6: Update `tests/test_cli.py`**

Replace with:

```python
# tests/test_cli.py
from click.testing import CliRunner

from ris_mcp.cli import ingest_main, mcp_main


def test_ingest_help_shows_flags_and_subcommands():
    r = CliRunner().invoke(ingest_main, ["--help"])
    assert r.exit_code == 0
    assert "--full" in r.output and "--delta" in r.output
    assert "coverage" in r.output


def test_ingest_requires_flag_or_subcommand():
    r = CliRunner().invoke(ingest_main, [])
    assert r.exit_code != 0
    assert "specify --full, --delta, or a subcommand" in r.output


def test_coverage_subcommand_help():
    r = CliRunner().invoke(ingest_main, ["coverage", "--help"])
    assert r.exit_code == 0
    assert "--out" in r.output


def test_mcp_help():
    r = CliRunner().invoke(mcp_main, ["--help"])
    assert r.exit_code == 0
```

- [ ] **Step 7:** Full pytest: `.venv/bin/pytest -v`. Previously 40 passed + 1 skipped; after this task expect 43 passed (40 + 3 coverage) + 1 skipped, with `test_cli.py` replaced by 4 new tests → net 43 + 4 - 2 old = 45 passed + 1 skipped. Verify 0 failures regardless of exact count.

- [ ] **Step 8: Verify CLI end-to-end**

```bash
.venv/bin/ris-ingest --help    # should show subcommands
.venv/bin/ris-ingest coverage --help
```

- [ ] **Step 9: Commit**

```
git add src/ris_mcp/cli.py src/ris_mcp/coverage.py tests/test_coverage.py tests/test_cli.py
git commit -m "Migrate CLI to click group and add ris-ingest coverage subcommand"
```

---

### Task 3: `import-from-hf` subcommand

**Files:**
- Create: `src/ris_mcp/hf_import.py`, `tests/test_hf_import.py`
- Modify: `src/ris_mcp/cli.py`

- [ ] **Step 1: Write failing tests** in `tests/test_hf_import.py`:

```python
# tests/test_hf_import.py
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from ris_mcp.hf_import import DatasetNotPublishedError, import_from_hf


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_import_from_hf_writes_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    db_bytes = b"SQLite format 3\x00" + b"\x00" * 100
    sha = hashlib.sha256(db_bytes).hexdigest()
    sha_file = f"{sha}  ris.db\n"

    def fake_download(*, repo_id: str, filename: str, **kwargs) -> str:
        staging = tmp_path / "_staging"
        staging.mkdir(exist_ok=True)
        p = staging / filename
        if filename == "ris.db":
            _write(p, db_bytes)
        elif filename == "ris.db.sha256":
            p.write_text(sha_file)
        else:
            raise ValueError(filename)
        return str(p)

    with patch("ris_mcp.hf_import.hf_hub_download", side_effect=fake_download):
        result = import_from_hf(repo="voilaj/austrian-caselaw")

    target = tmp_path / "ris.db"
    assert target.exists()
    assert target.read_bytes() == db_bytes
    assert result["path"] == str(target)
    assert result["bytes"] == len(db_bytes)


def test_import_from_hf_refuses_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    (tmp_path / "ris.db").write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        import_from_hf(repo="voilaj/austrian-caselaw")


def test_import_from_hf_raises_dataset_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    from huggingface_hub.utils import RepositoryNotFoundError
    with patch("ris_mcp.hf_import.hf_hub_download",
               side_effect=RepositoryNotFoundError("no such repo")):
        with pytest.raises(DatasetNotPublishedError):
            import_from_hf(repo="voilaj/austrian-caselaw")


def test_import_from_hf_verifies_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    db_bytes = b"content"
    wrong_sha = "0" * 64

    def fake_download(*, repo_id: str, filename: str, **kwargs) -> str:
        staging = tmp_path / "_staging"
        staging.mkdir(exist_ok=True)
        p = staging / filename
        if filename == "ris.db":
            _write(p, db_bytes)
        elif filename == "ris.db.sha256":
            p.write_text(f"{wrong_sha}  ris.db\n")
        return str(p)

    with patch("ris_mcp.hf_import.hf_hub_download", side_effect=fake_download):
        with pytest.raises(ValueError, match="sha256 mismatch"):
            import_from_hf(repo="voilaj/austrian-caselaw")
    assert not (tmp_path / "ris.db").exists()
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_hf_import.py -v` → ImportError.

- [ ] **Step 3: Implement `src/ris_mcp/hf_import.py`:**

```python
"""Download the pre-built ris-mcp SQLite corpus from HuggingFace."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import RepositoryNotFoundError

from .store import default_db_path


class DatasetNotPublishedError(RuntimeError):
    """Raised when the HF dataset repo does not exist yet."""


def import_from_hf(
    *,
    repo: str = "voilaj/austrian-caselaw",
    revision: str = "main",
    force: bool = False,
) -> dict[str, Any]:
    target = default_db_path()
    if target.exists() and not force:
        raise FileExistsError(
            f"{target} already exists; pass force=True to overwrite"
        )

    try:
        db_src = Path(hf_hub_download(
            repo_id=repo, filename="ris.db",
            revision=revision, repo_type="dataset",
        ))
        sha_src = Path(hf_hub_download(
            repo_id=repo, filename="ris.db.sha256",
            revision=revision, repo_type="dataset",
        ))
    except RepositoryNotFoundError as e:
        raise DatasetNotPublishedError(
            f"HuggingFace dataset {repo} not published yet. "
            "See https://jonashertner.github.io/ris-mcp for status."
        ) from e

    expected = sha_src.read_text().strip().split()[0]
    actual = hashlib.sha256(db_src.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(
            f"sha256 mismatch: expected {expected}, got {actual}. "
            f"Downloaded file not moved to {target}."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(db_src), str(target))

    size = target.stat().st_size
    return {"path": str(target), "bytes": size, "sha256": actual}
```

- [ ] **Step 4: Add the subcommand** in `src/ris_mcp/cli.py`, after the `coverage_cmd`:

```python
@ingest_main.command("import-from-hf")
@click.option("--repo", default="voilaj/austrian-caselaw",
              help="HuggingFace dataset repo")
@click.option("--revision", default="main", help="HF revision/branch/tag")
@click.option("--force", is_flag=True, help="Overwrite existing local DB")
def import_from_hf_cmd(repo: str, revision: str, force: bool) -> None:
    """Download the pre-built SQLite corpus from HuggingFace instead of ingesting locally."""
    from .hf_import import DatasetNotPublishedError, import_from_hf

    try:
        info = import_from_hf(repo=repo, revision=revision, force=force)
    except DatasetNotPublishedError as e:
        click.echo(f"error: {e}", err=True)
        raise SystemExit(2)
    except FileExistsError as e:
        click.echo(f"error: {e}", err=True)
        raise SystemExit(1)

    mb = info["bytes"] / (1024 * 1024)
    click.echo(f"downloaded {info['path']} ({mb:.1f} MB, sha256 verified)")
```

- [ ] **Step 5:** `.venv/bin/pytest -v` → all tests pass including 4 new hf_import tests.

- [ ] **Step 6: Verify CLI wiring**

```bash
.venv/bin/ris-ingest import-from-hf --help
```

Expected: help text including `--repo`, `--revision`, `--force`.

- [ ] **Step 7: Commit**

```
git add src/ris_mcp/hf_import.py src/ris_mcp/cli.py tests/test_hf_import.py
git commit -m "Add ris-ingest import-from-hf subcommand with sha256 verification"
```

---

### Task 4: Initial `docs/stats.json` placeholder + runbook

**Files:**
- Create: `docs/stats.json`, `docs/publishing-the-dataset.md`

- [ ] **Step 1: Create placeholder `docs/stats.json`**

Try the live coverage emitter first (it may work even against a partially-ingested DB from the background backfill):

```bash
.venv/bin/ris-ingest coverage --out docs/stats.json
cat docs/stats.json
```

If the open_db call fails or you want a deterministic placeholder, hand-create:

```json
{
  "generated_at": "2026-04-15T22:00:00Z",
  "total_decisions": 0,
  "total_laws": 0,
  "decisions_by_court": {},
  "corpus_span": {"earliest": null, "latest": null},
  "last_aenderungsdatum": null,
  "schema_version": 1,
  "note": "Placeholder — backfill in progress. Rerun `ris-ingest coverage` to refresh."
}
```

- [ ] **Step 2: Create `docs/publishing-the-dataset.md`**

```markdown
# Publishing the pre-built ris-mcp dataset to HuggingFace

Run after the full backfill (`ris-ingest --full`) completes on any one machine.

## 1. Generate a fresh stats report

```bash
ris-ingest coverage --out docs/stats.json
git add docs/stats.json
git commit -m "Refresh stats.json after backfill"
```

## 2. Prepare the DB for upload

```bash
DB=~/.local/share/ris-mcp/ris.db
sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);"
shasum -a 256 "$DB" | tee "${DB}.sha256"
```

## 3. Upload to HuggingFace

```bash
huggingface-cli login       # one-time
huggingface-cli upload voilaj/austrian-caselaw "$DB" ris.db
huggingface-cli upload voilaj/austrian-caselaw "${DB}.sha256" ris.db.sha256
```

If the repo does not exist, first:
`huggingface-cli repo create austrian-caselaw --type dataset --organization voilaj`.

## 4. Write a dataset card

Manually edit `README.md` on the HF repo (web UI). Include:
- Source: Austrian RIS Web Service v2.6 (data.bka.gv.at)
- License: CC0-1.0 (amtliches Werk per § 7 öUrhG)
- Schema reference: this repo's `src/ris_mcp/schema.sql`
- How to use: `pip install ris-mcp && ris-ingest import-from-hf`

## 5. Remove "coming soon" banners from the landing page

In `docs/index.html`, search for `<!-- HF-DATASET-PENDING -->` and remove each marked block (2 places). Commit:

```bash
git commit -m "Announce HF dataset availability"
```

## 6. Tag a docs-only release

```bash
git tag -a v0.2.1 -m "Pre-built dataset now available on HuggingFace"
git push origin v0.2.1
```
```

- [ ] **Step 3: Commit**

```
git add docs/stats.json docs/publishing-the-dataset.md
git commit -m "Add initial stats.json placeholder and dataset publishing runbook"
```

---

### Task 5: GitHub Pages landing page

**Files:**
- Create: `docs/index.html`

- [ ] **Step 1: Implement the single-page site**

Create `docs/index.html` with the content below. **Note on XSS safety:** the script block uses `textContent` and `document.createElement` exclusively — never `innerHTML` — when injecting values from `stats.json`. `stats.json` is generated by our own coverage command, but defending at the rendering boundary is still correct.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ris-mcp — Austrian RIS inside Claude</title>
<meta name="description" content="Local MCP server for Austrian court decisions and federal law. 700k+ decisions, fully offline, queryable from Claude." />
<script src="https://cdn.tailwindcss.com"></script>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚖️</text></svg>" />
</head>
<body class="bg-slate-50 text-slate-900 font-sans antialiased">

<header class="border-b border-slate-200 bg-white">
  <div class="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-2xl">⚖️</span>
      <span class="font-semibold">ris-mcp</span>
    </div>
    <nav class="flex gap-6 text-sm">
      <a href="#install" class="hover:text-slate-600">Install</a>
      <a href="#stats" class="hover:text-slate-600">Stats</a>
      <a href="#roadmap" class="hover:text-slate-600">Roadmap</a>
      <a href="https://github.com/jonashertner/ris-mcp" class="hover:text-slate-600">GitHub</a>
    </nav>
  </div>
</header>

<section class="max-w-5xl mx-auto px-6 py-20">
  <h1 class="text-4xl md:text-5xl font-bold tracking-tight">Austrian case law + federal statutes, inside Claude.</h1>
  <p class="mt-6 text-lg text-slate-600 max-w-3xl">
    <code>ris-mcp</code> is a local MCP server that mirrors the Austrian Rechtsinformationssystem
    (RIS) into a searchable SQLite database, so Claude (Desktop, Code, claude.ai) can answer
    legal-research questions against the full corpus of published Austrian court decisions and
    consolidated federal law. Free, open, CC0 data.
  </p>
  <div class="mt-10 flex flex-wrap gap-3">
    <a href="#install" class="bg-slate-900 text-white px-5 py-3 rounded-lg font-medium hover:bg-slate-800">Install</a>
    <a href="https://github.com/jonashertner/ris-mcp" class="border border-slate-300 px-5 py-3 rounded-lg font-medium hover:border-slate-400">GitHub</a>
  </div>
</section>

<section class="max-w-5xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-8">
  <div>
    <div class="text-3xl">🏛️</div>
    <h2 class="mt-3 font-semibold">All published case law</h2>
    <p class="mt-2 text-slate-600 text-sm">OGH, VfGH, VwGH, BVwG, 9 Landesverwaltungsgerichte, and special-body decisions — every judikatur source RIS publishes.</p>
  </div>
  <div>
    <div class="text-3xl">📚</div>
    <h2 class="mt-3 font-semibold">Consolidated federal law</h2>
    <p class="mt-2 text-slate-600 text-sm">Every § and Artikel of Austrian Bundesrecht in its current Fassung, searchable alongside the case law that applies it.</p>
  </div>
  <div>
    <div class="text-3xl">⚡</div>
    <h2 class="mt-3 font-semibold">Sub-ms local search</h2>
    <p class="mt-2 text-slate-600 text-sm">SQLite + FTS5 BM25 ranking. Your queries never leave your machine. Works offline.</p>
  </div>
</section>

<section id="install" class="max-w-5xl mx-auto px-6 py-16 border-t border-slate-200">
  <h2 class="text-3xl font-bold">Install</h2>

  <!-- HF-DATASET-PENDING -->
  <div class="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm">
    <strong>Status:</strong> the pre-built dataset is being uploaded (full backfill takes 2–3 days).
    Until it lands on HuggingFace, step&nbsp;3 below will fail with a friendly message telling you
    to run <code>ris-ingest --full</code> locally. Watch the <a href="#stats" class="underline">stats</a> section for updates.
  </div>
  <!-- /HF-DATASET-PENDING -->

  <ol class="mt-8 space-y-6 text-slate-800">
    <li>
      <div class="font-medium">1. Install <code>uv</code> (the Python package runner).</div>
      <pre class="mt-2 bg-slate-900 text-slate-100 rounded-lg p-4 text-sm overflow-x-auto"><code>curl -LsSf https://astral.sh/uv/install.sh | sh</code></pre>
      <p class="text-sm text-slate-500 mt-1">See <a class="underline" href="https://docs.astral.sh/uv/">docs.astral.sh/uv</a> for Windows instructions.</p>
    </li>
    <li>
      <div class="font-medium">2. Register the MCP server with Claude.</div>
      <pre class="mt-2 bg-slate-900 text-slate-100 rounded-lg p-4 text-sm overflow-x-auto"><code>claude mcp add ris -- uvx --from git+https://github.com/jonashertner/ris-mcp ris-mcp serve</code></pre>
      <p class="text-sm text-slate-500 mt-1">After <code>ris-mcp</code> is published on PyPI, this simplifies to <code>uvx ris-mcp serve</code>.</p>
    </li>
    <li>
      <div class="font-medium">3. Download the pre-built corpus (one-time, ~12 GB).</div>
      <pre class="mt-2 bg-slate-900 text-slate-100 rounded-lg p-4 text-sm overflow-x-auto"><code>uvx --from git+https://github.com/jonashertner/ris-mcp ris-ingest import-from-hf</code></pre>
      <p class="text-sm text-slate-500 mt-1">Or run your own ingest with <code>ris-ingest --full</code> (2–3 days).</p>
    </li>
  </ol>

  <h3 class="mt-10 text-xl font-semibold">Claude Desktop config</h3>
  <p class="text-sm text-slate-600 mt-2">If you'd rather hand-edit <code>~/Library/Application Support/Claude/claude_desktop_config.json</code>:</p>
  <pre class="mt-3 bg-slate-900 text-slate-100 rounded-lg p-4 text-sm overflow-x-auto"><code>{
  "mcpServers": {
    "ris": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jonashertner/ris-mcp", "ris-mcp", "serve"]
    }
  }
}</code></pre>
</section>

<section class="max-w-5xl mx-auto px-6 py-16 border-t border-slate-200">
  <h2 class="text-3xl font-bold">Why not <code>philrox/ris-mcp-ts</code>?</h2>
  <p class="mt-4 text-slate-600 max-w-3xl">A legitimate TypeScript MCP wrapper for RIS already exists. It's a great fit for casual queries. <code>ris-mcp</code> is a different trade-off: build and maintain a local mirror so you get better answers.</p>
  <div class="mt-8 overflow-x-auto">
    <table class="w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
      <thead class="bg-slate-100 text-left">
        <tr><th class="p-3">Capability</th><th class="p-3">philrox (live proxy)</th><th class="p-3">ris-mcp (local mirror)</th></tr>
      </thead>
      <tbody class="divide-y divide-slate-200">
        <tr><td class="p-3">Claude can query Austrian law</td><td class="p-3">✅</td><td class="p-3">✅</td></tr>
        <tr><td class="p-3">Search quality</td><td class="p-3">RIS field-based keyword</td><td class="p-3">FTS5 BM25 over full text</td></tr>
        <tr><td class="p-3">Latency</td><td class="p-3">2–5 s per query</td><td class="p-3">&lt; 10 ms</td></tr>
        <tr><td class="p-3">Works offline</td><td class="p-3">❌</td><td class="p-3">✅</td></tr>
        <tr><td class="p-3">Survives RIS API outages</td><td class="p-3">❌</td><td class="p-3">✅</td></tr>
        <tr><td class="p-3">Citation graph (future)</td><td class="p-3">❌</td><td class="p-3">Phase 2</td></tr>
      </tbody>
    </table>
  </div>
</section>

<section id="stats" class="max-w-5xl mx-auto px-6 py-16 border-t border-slate-200">
  <h2 class="text-3xl font-bold">Corpus</h2>
  <div id="stats-loading" class="mt-4 text-slate-500 text-sm">Loading stats…</div>
  <div id="stats-body" class="mt-6 hidden">
    <div class="grid md:grid-cols-3 gap-6">
      <div class="bg-white border border-slate-200 rounded-lg p-5">
        <div class="text-sm text-slate-500">Decisions</div>
        <div id="stats-decisions" class="text-4xl font-bold mt-1">—</div>
      </div>
      <div class="bg-white border border-slate-200 rounded-lg p-5">
        <div class="text-sm text-slate-500">Laws (articles)</div>
        <div id="stats-laws" class="text-4xl font-bold mt-1">—</div>
      </div>
      <div class="bg-white border border-slate-200 rounded-lg p-5">
        <div class="text-sm text-slate-500">Last refreshed</div>
        <div id="stats-refreshed" class="text-lg font-medium mt-1">—</div>
      </div>
    </div>
    <h3 class="mt-10 font-semibold">By court</h3>
    <div id="stats-by-court" class="mt-3 grid md:grid-cols-3 gap-2 text-sm"></div>
  </div>
</section>

<section id="roadmap" class="max-w-5xl mx-auto px-6 py-16 border-t border-slate-200">
  <h2 class="text-3xl font-bold">Roadmap</h2>
  <ul class="mt-6 space-y-3 text-slate-700">
    <li>✅ <strong>Phase 1</strong> — ingester, SQLite/FTS5 store, three MCP tools.</li>
    <li>🚧 <strong>Phase 1.5</strong> — PyPI release, public landing page, pre-built HF dataset.</li>
    <li>🔜 <strong>Phase 2</strong> — resolved citation graph: find_leading_cases, find_citations, find_appeal_chain.</li>
    <li>🔜 <strong>Phase 3</strong> — semantic reranking and a remote hosted MCP endpoint (no local install).</li>
    <li>🔜 <strong>Phase 4</strong> — Materialien: RV-Begründungen and Stenographische Protokolle for teleological interpretation.</li>
    <li>🔜 <strong>Phase 5</strong> — Landesrecht, commentary integration if viable.</li>
  </ul>
</section>

<footer class="border-t border-slate-200 mt-16">
  <div class="max-w-5xl mx-auto px-6 py-10 text-sm text-slate-600">
    <p>
      Code: MIT. Data: CC0-1.0 — Austrian RIS content is amtliches Werk per § 7 öUrhG.
      Not legal advice. Builds on the documentation work of
      <a class="underline" href="https://github.com/ximex/ris-bka">ximex/ris-bka</a>,
      learns from
      <a class="underline" href="https://github.com/philrox/ris-mcp-ts">philrox/ris-mcp-ts</a>,
      <a class="underline" href="https://github.com/PhilippTh/ris-API-wrapper">PhilippTh/ris-API-wrapper</a>, and
      <a class="underline" href="https://opencaselaw.ch">opencaselaw.ch</a>.
    </p>
  </div>
</footer>

<script>
  (async () => {
    const loading = document.getElementById("stats-loading");
    const body = document.getElementById("stats-body");
    const courtsEl = document.getElementById("stats-by-court");

    const makeRow = (court, count, fmt) => {
      const row = document.createElement("div");
      row.className = "flex justify-between bg-white border border-slate-200 rounded-lg p-3";
      const name = document.createElement("span");
      name.textContent = court;
      const num = document.createElement("span");
      num.className = "font-medium";
      num.textContent = fmt(count);
      row.appendChild(name);
      row.appendChild(num);
      return row;
    };

    const makeEmpty = (msg) => {
      const d = document.createElement("div");
      d.className = "text-slate-500";
      d.textContent = msg;
      return d;
    };

    try {
      const r = await fetch("stats.json", { cache: "no-cache" });
      if (!r.ok) throw new Error("no stats");
      const s = await r.json();
      const fmt = (n) => (n || 0).toLocaleString("en-US");

      document.getElementById("stats-decisions").textContent = fmt(s.total_decisions);
      document.getElementById("stats-laws").textContent = fmt(s.total_laws);
      const refreshed = s.generated_at
        ? s.generated_at.slice(0, 19).replace("T", " ") + " UTC"
        : "—";
      document.getElementById("stats-refreshed").textContent = refreshed;

      const byCourt = s.decisions_by_court || {};
      const entries = Object.entries(byCourt).sort((a, b) => b[1] - a[1]);
      if (entries.length === 0) {
        courtsEl.appendChild(makeEmpty("No decisions yet — backfill in progress."));
      } else {
        for (const [court, count] of entries) {
          courtsEl.appendChild(makeRow(court, count, fmt));
        }
      }

      loading.classList.add("hidden");
      body.classList.remove("hidden");
    } catch (e) {
      loading.textContent = "Stats not available yet.";
    }
  })();
</script>
</body>
</html>
```

- [ ] **Step 2: Local preview**

```bash
cd docs && python3 -m http.server 8765
```

Open `http://localhost:8765` in a browser. Verify:
- Layout loads
- `stats.json` renders (even if zeros)
- All links work

Kill the server once satisfied.

- [ ] **Step 3: Commit**

```
git add docs/index.html
git commit -m "Add GitHub Pages landing page"
```

---

### Task 6: Enable Pages in repo (manual, documented)

**Files:**
- None (repo settings change)

- [ ] **Step 1: Push to main first**

```bash
git push origin main
```

- [ ] **Step 2: Enable Pages**

In the GitHub web UI:
1. Go to `https://github.com/jonashertner/ris-mcp/settings/pages`
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **`/docs`**
4. Click Save

Wait ~1 min for the first build. Visit `https://jonashertner.github.io/ris-mcp/`.

- [ ] **Step 3: Verify the live site renders**

Confirm:
- `https://jonashertner.github.io/ris-mcp/` loads
- `https://jonashertner.github.io/ris-mcp/stats.json` is reachable (browser should see JSON)

If 404: wait another 2 min, Pages first-build takes time.

- [ ] **Step 4: No commit needed** (repo settings only). Note the live URL for the release workflow's description.

---

### Task 7: PyPI release workflow (Trusted Publisher)

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Manual (user) — register the project on PyPI**

User performs this once:
1. `https://pypi.org/manage/account/publishing/` → add a pending publisher
   - PyPI project name: `ris-mcp`
   - Owner: `jonashertner`
   - Repository: `ris-mcp`
   - Workflow filename: `release.yml`
   - Environment: `pypi`
2. In GitHub: repo Settings → Environments → New environment → name `pypi`. No protection rules needed for Phase 1.5.

If the user hasn't done this yet when we push the tag, the first run fails; fix and re-tag.

- [ ] **Step 2: Create `.github/workflows/release.yml`**

```yaml
name: release
on:
  push:
    tags: ['v*']
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 3: Commit**

```
git add .github/workflows/release.yml
git commit -m "Add PyPI release workflow via Trusted Publisher"
```

---

### Task 8: README overhaul + tag v0.2.0

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Simplify README**

Replace the current README's content:

```markdown
# ris-mcp

> **👉 For end users: see [jonashertner.github.io/ris-mcp](https://jonashertner.github.io/ris-mcp/) for the three-command install.**

Local MCP server for the Austrian Rechtsinformationssystem (RIS) — court decisions and consolidated federal law, queryable from Claude (Code, Desktop, claude.ai).

[![CI](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/jonashertner/ris-mcp/actions/workflows/ci.yml)

## What

`ris-mcp` maintains a locally-mirrored, FTS5-indexed SQLite copy of the full Austrian RIS corpus and exposes it to Claude via MCP. Compare to [`philrox/ris-mcp-ts`](https://github.com/philrox/ris-mcp-ts), which is a thin live-API proxy: local mirror wins on search quality, latency, offline capability, and future citation-graph/reranking work.

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

- [ximex/ris-bka](https://github.com/ximex/ris-bka) — RIS OGD documentation
- [philrox/ris-mcp-ts](https://github.com/philrox/ris-mcp-ts) — different design, same goal
- [PhilippTh/ris-API-wrapper](https://github.com/PhilippTh/ris-API-wrapper) — Python wrapper precedent
- [opencaselaw.ch](https://opencaselaw.ch) — architectural inspiration
```

- [ ] **Step 2: Commit**

```
git add README.md
git commit -m "Point README to landing page; collapse end-user instructions"
```

- [ ] **Step 3: Final verification**

```bash
.venv/bin/pytest -v                    # all pass + 1 skipped
.venv/bin/ruff check src tests         # clean
.venv/bin/ris-ingest --help
.venv/bin/ris-ingest coverage --help
.venv/bin/ris-ingest import-from-hf --help
```

All must succeed. No skip allowed.

- [ ] **Step 4: Tag and push**

```bash
git push origin main
git tag -a v0.2.0 -m "Phase 1.5: PyPI release, landing page, import-from-hf"
git push origin v0.2.0
```

- [ ] **Step 5: Watch the release workflow**

```bash
gh run watch
```

If PyPI publish fails and Task 7 Step 1 (PyPI Trusted Publisher registration) hasn't been done, fix, re-tag as `v0.2.0-rc1`, re-test.

If Pages hasn't been enabled (Task 6 not done): site won't render — do Task 6 now.

- [ ] **Step 6: Post-release sanity check**

- `https://pypi.org/project/ris-mcp/0.2.0/` exists
- `pip install ris-mcp==0.2.0` into a fresh venv works
- `uvx ris-mcp serve` (after publish) starts the server (will error because no DB, expected)
- `https://jonashertner.github.io/ris-mcp/` renders

Report done only after each check passes.

---

## Self-review

**Spec coverage:** §4.1 → T7; §4.2 → T3; §4.3 → T2; §4.4 → T5+T6; §4.5 → backfill started pre-T1 + runbook in T4; §4.6 → T8. ✓

**Placeholder scan:** No "TBD". Manual steps (PyPI registration, Pages toggle) are explicit user actions with URLs.

**Type consistency:** `generate_coverage`, `import_from_hf`, `DatasetNotPublishedError`, `coverage_cmd`, `import_from_hf_cmd`, `ingest_main` (now `click.group`) — consistent across tasks.

**XSS:** Landing page script uses `textContent` + `document.createElement` only; no `innerHTML` with dynamic content.
