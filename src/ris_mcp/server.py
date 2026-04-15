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

    # Tool registration is added in Tasks 8–10.
    from .tools import get_decision as t_gd
    from .tools import get_law as t_gl
    from .tools import search_decisions as t_sd

    t_sd.register(server, conn)
    t_gd.register(server, conn)
    t_gl.register(server, conn)
    return server


async def serve() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
