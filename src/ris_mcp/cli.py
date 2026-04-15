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
