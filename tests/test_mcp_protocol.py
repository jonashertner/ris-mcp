from __future__ import annotations

import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_stdio_handshake_lists_and_calls_tools(tmp_path):
    """Exercise the installed protocol surface, not only the Python helpers."""
    env = os.environ.copy()
    env["RIS_MCP_DATA_DIR"] = str(tmp_path)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from ris_mcp.server import main; main()"],
        env=env,
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        listed = await session.list_tools()
        result = await session.call_tool(
            "search_decisions", {"query": "Verfassungsrecht"}
        )

    assert initialized.serverInfo.name == "ris-mcp"
    assert {tool.name for tool in listed.tools} == {
        "search_decisions",
        "get_decision",
        "get_law",
    }
    assert result.isError is not True
    assert result.content[0].text == "[]"
