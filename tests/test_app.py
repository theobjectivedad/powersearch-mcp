from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from mcp.types import TextContent
from pytest import MonkeyPatch

from powersearch_mcp import app
from powersearch_mcp.powersearch import MessageSink, SearchResultRecord


@pytest_asyncio.fixture
async def mcp_client() -> AsyncIterator[Client[FastMCPTransport]]:
    client: Client[FastMCPTransport] = Client(app.mcp)
    async with client:
        yield client


@pytest.mark.asyncio
async def test_exposes_tools_and_prompts(
    mcp_client: Client[FastMCPTransport],
) -> None:
    tools = await mcp_client.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {"search", "fetch_url", "summarize_search"} <= tool_names

    prompts = await mcp_client.list_prompts()
    prompt_by_name = {prompt.name: prompt for prompt in prompts}

    assert "internet_search_prompt" in prompt_by_name
    assert prompt_by_name["internet_search_prompt"].title == "Internet Search"
    assert "summarize_internet_search_prompt" in prompt_by_name
    assert (
        prompt_by_name["summarize_internet_search_prompt"].title
        == "Summarize Internet Search"
    )


@pytest.mark.asyncio
async def test_prompt_renders_goal_and_time_range(
    mcp_client: Client[FastMCPTransport],
) -> None:
    prompt = await mcp_client.get_prompt(
        "internet_search_prompt",
        {"goal": "find docs", "time_range": "month"},
    )

    message_content = prompt.messages[0].content
    assert isinstance(message_content, TextContent)

    message_text = message_content.text

    assert "Goal: find docs" in message_text
    assert "time_range='month'" in message_text


@pytest.mark.asyncio
async def test_search_tool_returns_structured_results(
    mcp_client: Client[FastMCPTransport], monkeypatch: MonkeyPatch
) -> None:
    async def fake_search(
        ctx: MessageSink, query: str, time_range: str | None = None
    ) -> list[SearchResultRecord]:
        return [
            SearchResultRecord(
                title="Example Title",
                url="http://example.com",
                content="Clean content",
            )
        ]

    monkeypatch.setattr(app, "run_search", fake_search)

    result = await mcp_client.call_tool("search", {"query": "example"})

    assert not result.is_error
    assert result.structured_content
    assert result.structured_content["result"][0]["title"] == "Example Title"
    assert result.data[0]["url"] == "http://example.com"


@pytest.mark.asyncio
async def test_fetch_tool_returns_text_payload(
    mcp_client: Client[FastMCPTransport], monkeypatch: MonkeyPatch
) -> None:
    async def fake_fetch(
        ctx: MessageSink, url: str, fetch_timeout_ms: int = 1234
    ) -> str:
        return f"body from {url}"

    monkeypatch.setattr(app, "run_fetch_url", fake_fetch)

    result = await mcp_client.call_tool(
        "fetch_url",
        {"url": "http://example.com/test"},
    )

    assert not result.is_error
    assert result.data == "body from http://example.com/test"
    first_content = result.content[0]
    assert isinstance(first_content, TextContent)
    assert first_content.text.startswith("body from http://example.com")


@pytest.mark.asyncio
async def test_summarize_search_tool_returns_structured_result(
    mcp_client: Client[FastMCPTransport], monkeypatch: MonkeyPatch
) -> None:
    async def fake_summary(
        ctx: MessageSink,
        query: str,
        intent: str,
        time_range: str | None = None,
        max_results: int | None = None,
        map_reduce: bool = False,
    ) -> dict[str, object]:
        return {
            "summary": "done",
            "sources": ["http://example.com"],
        }

    monkeypatch.setattr(app, "run_summarize_search", fake_summary)

    result = await mcp_client.call_tool(
        "summarize_search",
        {"query": "example", "intent": "summarize"},
    )

    assert not result.is_error
    assert result.structured_content
    assert result.structured_content["summary"] == "done"
    assert result.structured_content["sources"] == ["http://example.com"]


@pytest.mark.asyncio
async def test_search_invalid_time_range_surfaces_error(
    mcp_client: Client[FastMCPTransport],
) -> None:
    result = await mcp_client.call_tool(
        "search",
        {"query": "q", "time_range": "week"},
        raise_on_error=False,
    )

    assert result.is_error
    first_content = result.content[0]
    assert isinstance(first_content, TextContent)
    assert first_content.text.startswith("Internal error: Error calling tool")


@pytest.mark.asyncio
async def test_health_route_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
