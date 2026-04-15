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
        raise SystemExit(2) from e
    except FileExistsError as e:
        click.echo(f"error: {e}", err=True)
        raise SystemExit(1) from e

    mb = info["bytes"] / (1024 * 1024)
    click.echo(f"downloaded {info['path']} ({mb:.1f} MB, sha256 verified)")


@click.group(name="ris-mcp", invoke_without_command=True)
@click.pass_context
def mcp_main(ctx: click.Context) -> None:
    """Austrian RIS plug-in for Claude — run the MCP server or run diagnostics."""
    if ctx.invoked_subcommand is None:
        mcp_server.main()


@mcp_main.command("serve")
def serve_cmd() -> None:
    """Run the MCP server over stdio (default when no subcommand is given)."""
    mcp_server.main()


@mcp_main.command("doctor")
def doctor_cmd() -> None:
    """Check your ris-mcp installation for common problems."""
    from .doctor import format_report, run_diagnostics
    click.echo(format_report(run_diagnostics()))
