"""MCP server exposing PowerSearch search and fetch tools."""

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSessionT
from mcp.shared.context import LifespanContextT
from pydantic import Field

from .powersearch import (
    SearchResultRecord,
)
from .powersearch import (
    fetch_url as run_fetch_url,
)
from .powersearch import (
    search as run_search,
)

mcp = FastMCP(
    name="powersearch",
    instructions=(
        "Internet search plus page fetch. "
        "search(query, time_range=day|month|year) returns results with title, url, and "
        "cleaned markdown content. fetch_url(url, fetch_timeout_ms) fetches a single page "
        "and returns cleaned markdown. Use for public web lookups; do not expect internal data."
    ),
)


@mcp.prompt(title="Internet Search")
def internet_search_prompt(
    goal: Annotated[str, Field(description="What you are trying to find")],
    time_range: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional recency bias: day, month, or year.",
        ),
    ] = None,
) -> str:
    """Lightweight prompt for agents to run a web lookup with powersearch tools."""

    recency_hint = (
        f" Include time_range='{time_range}' if you need recent results."
        if time_range
        else ""
    )

    return (
        "You can search the public web via the powersearch MCP server.\n"
        f"Goal: {goal}\n"
        f"- Call powersearch/search with the goal as the query.{recency_hint}\n"
        "- Results include cleaned content; call fetch_url only to refresh a specific URL.\n"
        "- Summarize briefly and cite URLs; do not invent sources."
    )


@mcp.tool()
async def search(
    ctx: Context[ServerSessionT, LifespanContextT],
    query: Annotated[str, Field(description="Search query string")],
    time_range: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Restrict results to a timeframe: day, month, or year. "
                "Leave empty to search all time."
            ),
        ),
    ] = None,
) -> list[SearchResultRecord]:
    """MCP tool wrapper for the core search implementation."""

    return await run_search(ctx=ctx, query=query, time_range=time_range)


@mcp.tool()
async def fetch_url(
    ctx: Context[ServerSessionT, LifespanContextT],
    url: Annotated[
        str, Field(..., description="URL to fetch from the Internet")
    ],
    fetch_timeout_ms: Annotated[
        int,
        Field(
            default=10 * 1000,
            description=(
                "Per-request timeout in milliseconds applied to the upstream fetch."
            ),
        ),
    ] = 10 * 1000,
) -> str:
    """MCP tool wrapper for fetching and cleaning URL content."""

    return await run_fetch_url(
        ctx=ctx,
        url=url,
        fetch_timeout_ms=fetch_timeout_ms,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
