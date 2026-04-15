"""MCP server (stdio). Wires SDK to tool functions in ris_mcp.tools.*"""
from __future__ import annotations

import asyncio
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server

from .store import open_db

log = logging.getLogger(__name__)


def build_server() -> Server:
    server = Server("ris-mcp")
    conn = open_db()

    from .tools import search_decisions as t_sd
    # Tasks 9 and 10 add: get_decision, get_law
    tools = {t_sd.TOOL.name: t_sd}

    @server.list_tools()
    async def _list():
        return [t.TOOL for t in tools.values()]

    @server.call_tool()
    async def _call(name: str, arguments: dict):
        t = tools.get(name)
        if t is None:
            raise ValueError(f"unknown tool: {name}")
        return await t.handle(conn, arguments)

    return server


async def serve() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
