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
def ingest_main(
    full: bool, delta: bool, applikation: str | None, include_bundesrecht: bool
) -> None:
    if not (full or delta):
        raise click.UsageError("specify --full or --delta")

    async def run():
        conn = open_db()
        async with RisClient() as client:
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
