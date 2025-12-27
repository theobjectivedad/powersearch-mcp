from __future__ import annotations

import pytest
from fastmcp import Client

from powersearch_mcp.app import mcp


@pytest.mark.asyncio
async def test_tools_via_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(
        *, ctx: object, query: str, time_range: str | None
    ) -> list[dict[str, str]]:
        return [
            {
                "title": "Example",
                "url": "https://example.com",
                "content": "Example content",
            }
        ]

    async def fake_fetch_url(
        *, ctx: object, url: str, fetch_timeout_ms: int
    ) -> str:
        return f"fetched:{url}:{fetch_timeout_ms}"

    monkeypatch.setattr("powersearch_mcp.app.run_search", fake_search)
    monkeypatch.setattr("powersearch_mcp.app.run_fetch_url", fake_fetch_url)

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        assert "search" in tool_names
        assert "fetch_url" in tool_names

        search_result = await client.call_tool(
            "search",
            {"query": "alpha", "time_range": None},
        )
        assert "Example" in str(search_result.data)

        fetch_result = await client.call_tool(
            "fetch_url",
            {"url": "https://example.com", "fetch_timeout_ms": 5000},
        )
        assert "fetched:https://example.com:5000" in str(fetch_result.data)
